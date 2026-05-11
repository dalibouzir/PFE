from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import func, select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.models.batch import Batch
from app.models.commercial_invoice import CommercialInvoice, CommercialInvoiceLine
from app.models.commercial_order import CommercialOrder, CommercialOrderLine
from app.models.enums import BatchStatus, CommercialOrderStatus, InvoiceStatus
from app.models.farmer_advance import FarmerAdvance
from app.models.global_charge import GlobalCharge
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.stock import Stock
from app.models.treasury_transaction import TreasuryTransaction

REPORT_PATH = ROOT_DIR / "reports" / "demo_data_integrity_report.md"

EPS = 1e-6


@dataclass
class Finding:
    severity: str
    check: str
    table: str
    record_ref: str
    message: str
    suggested_fix: str


def _is_close(a: float, b: float, tol: float = 1e-3) -> bool:
    return abs(float(a) - float(b)) <= tol


def _fmt_float(v: float) -> str:
    return f"{float(v):.4f}"


def _severity_weight(severity: str) -> int:
    return {
        "critical": 10,
        "high": 5,
        "medium": 2,
        "low": 1,
    }.get(severity, 1)


def _add_finding(
    findings: list[Finding],
    *,
    severity: str,
    check: str,
    table: str,
    record_ref: str,
    message: str,
    suggested_fix: str,
) -> None:
    findings.append(
        Finding(
            severity=severity,
            check=check,
            table=table,
            record_ref=record_ref,
            message=message,
            suggested_fix=suggested_fix,
        )
    )


def _validate_stocks_and_reservations(db, findings: list[Finding], checked: dict[str, int]) -> None:
    stocks = db.scalars(select(Stock)).all()
    checked["stocks"] = len(stocks)

    for stock in stocks:
        ref = f"stock:{stock.id}"
        if stock.total_stock_kg < -EPS:
            _add_finding(
                findings,
                severity="critical",
                check="no_negative_stock",
                table="stocks",
                record_ref=ref,
                message=f"total_stock_kg is negative ({_fmt_float(stock.total_stock_kg)}).",
                suggested_fix="Recompute stock from inputs and lot reservations; clamp to >= 0.",
            )
        if stock.reserved_in_lots_kg < -EPS:
            _add_finding(
                findings,
                severity="critical",
                check="no_negative_reserved_stock",
                table="stocks",
                record_ref=ref,
                message=f"reserved_in_lots_kg is negative ({_fmt_float(stock.reserved_in_lots_kg)}).",
                suggested_fix="Recompute reserved quantity from active lots; clamp to >= 0.",
            )
        if stock.reserved_in_lots_kg - stock.total_stock_kg > EPS:
            _add_finding(
                findings,
                severity="critical",
                check="reserved_not_exceed_total",
                table="stocks",
                record_ref=ref,
                message=(
                    "reserved_in_lots_kg exceeds total_stock_kg "
                    f"({_fmt_float(stock.reserved_in_lots_kg)} > {_fmt_float(stock.total_stock_kg)})."
                ),
                suggested_fix="Release invalid reservations or increase total stock via validated inputs.",
            )

        expected_available = max(float(stock.total_stock_kg) - float(stock.reserved_in_lots_kg), 0.0)
        if not _is_close(float(stock.quantity), expected_available):
            _add_finding(
                findings,
                severity="high",
                check="available_stock_consistency",
                table="stocks",
                record_ref=ref,
                message=(
                    f"quantity ({_fmt_float(stock.quantity)}) != total-reserved "
                    f"({_fmt_float(expected_available)})."
                ),
                suggested_fix="Run stock snapshot synchronization to align available quantity.",
            )

    # Reservation reconciliation: active lots per product should match reserved stock per product.
    active_rows = db.execute(
        select(Batch.product_id, func.coalesce(func.sum(Batch.initial_qty), 0.0))
        .where(Batch.status.in_([BatchStatus.CREATED, BatchStatus.IN_PROGRESS]))
        .group_by(Batch.product_id)
    ).all()
    reserved_by_product = {row[0]: float(row[1] or 0.0) for row in active_rows}

    stock_by_product = {
        stock.product_id: stock
        for stock in stocks
    }

    all_products = set(reserved_by_product.keys()) | set(stock_by_product.keys())
    for product_id in all_products:
        expected_reserved = float(reserved_by_product.get(product_id, 0.0))
        stock = stock_by_product.get(product_id)
        if stock is None:
            _add_finding(
                findings,
                severity="critical",
                check="reservation_stock_row_exists",
                table="stocks",
                record_ref=f"product:{product_id}",
                message="Active lot reservation exists but no stock row found for product.",
                suggested_fix="Create missing stock row for product and recompute stock aggregates.",
            )
            continue

        if not _is_close(float(stock.reserved_in_lots_kg), expected_reserved):
            _add_finding(
                findings,
                severity="high",
                check="active_lot_reservation_match",
                table="stocks,batches",
                record_ref=f"product:{product_id}",
                message=(
                    f"reserved_in_lots_kg ({_fmt_float(stock.reserved_in_lots_kg)}) != sum(active lot initial_qty) "
                    f"({_fmt_float(expected_reserved)})."
                ),
                suggested_fix="Rebuild reservation ledger from active lots and update stock.reserved_in_lots_kg.",
            )


def _validate_batches_and_process(db, findings: list[Finding], checked: dict[str, int]) -> None:
    batches = db.scalars(select(Batch)).all()
    checked["batches"] = len(batches)

    steps = db.scalars(select(ProcessStep)).all()
    checked["process_steps"] = len(steps)

    steps_by_batch: dict[Any, list[ProcessStep]] = {}
    for step in steps:
        steps_by_batch.setdefault(step.batch_id, []).append(step)

    for step in steps:
        ref = f"process_step:{step.id}"
        if float(step.qty_in) < -EPS or float(step.qty_out) < -EPS:
            _add_finding(
                findings,
                severity="critical",
                check="process_qty_non_negative",
                table="process_steps",
                record_ref=ref,
                message=(
                    f"Negative process quantity: qty_in={_fmt_float(step.qty_in)}, qty_out={_fmt_float(step.qty_out)}."
                ),
                suggested_fix="Recompute step quantities from upstream valid step/output.",
            )
        if float(step.qty_out) - float(step.qty_in) > EPS:
            _add_finding(
                findings,
                severity="high",
                check="process_output_not_exceed_input",
                table="process_steps",
                record_ref=ref,
                message=(
                    f"qty_out exceeds qty_in ({_fmt_float(step.qty_out)} > {_fmt_float(step.qty_in)})."
                ),
                suggested_fix="Enforce step-level loss constraints or flag exceptional yield rules explicitly.",
            )

        computed_loss_kg = float(step.qty_in) - float(step.qty_out)
        if not _is_close(float(step.waste_qty), computed_loss_kg):
            _add_finding(
                findings,
                severity="medium",
                check="step_loss_kg_consistency",
                table="process_steps",
                record_ref=ref,
                message=(
                    f"waste_qty ({_fmt_float(step.waste_qty)}) != qty_in-qty_out ({_fmt_float(computed_loss_kg)})."
                ),
                suggested_fix="Synchronize waste_qty with qty_in - qty_out.",
            )

        if not _is_close(float(step.normalized_loss_value), computed_loss_kg):
            _add_finding(
                findings,
                severity="medium",
                check="step_normalized_loss_consistency",
                table="process_steps",
                record_ref=ref,
                message=(
                    f"normalized_loss_value ({_fmt_float(step.normalized_loss_value)}) != qty_in-qty_out ({_fmt_float(computed_loss_kg)})."
                ),
                suggested_fix="Normalize step loss values after unit conversions.",
            )

    for batch in batches:
        ref = f"batch:{batch.id}"
        if float(batch.initial_qty) < -EPS or float(batch.current_qty) < -EPS:
            _add_finding(
                findings,
                severity="critical",
                check="batch_qty_non_negative",
                table="batches",
                record_ref=ref,
                message=f"Negative batch quantities (initial={_fmt_float(batch.initial_qty)}, current={_fmt_float(batch.current_qty)}).",
                suggested_fix="Reset batch quantities from valid process-step chain.",
            )

        batch_steps = sorted(
            steps_by_batch.get(batch.id, []),
            key=lambda s: (int(s.sequence_order or 0), s.date, s.created_at, s.id),
        )

        if batch_steps:
            latest = batch_steps[-1]
            if not _is_close(float(batch.current_qty), float(latest.qty_out)):
                _add_finding(
                    findings,
                    severity="high",
                    check="batch_current_qty_matches_latest_step",
                    table="batches,process_steps",
                    record_ref=ref,
                    message=(
                        f"batch.current_qty ({_fmt_float(batch.current_qty)}) != latest step.qty_out ({_fmt_float(latest.qty_out)})."
                    ),
                    suggested_fix="Recompute batch.current_qty from latest process step output.",
                )

            # Validate chain continuity between consecutive steps.
            prev_out = float(batch.initial_qty)
            for step in batch_steps:
                if not _is_close(float(step.qty_in), prev_out):
                    _add_finding(
                        findings,
                        severity="high",
                        check="process_chain_continuity",
                        table="process_steps",
                        record_ref=f"process_step:{step.id}",
                        message=(
                            f"qty_in ({_fmt_float(step.qty_in)}) != previous output ({_fmt_float(prev_out)})."
                        ),
                        suggested_fix="Rebuild process chain inputs from previous step outputs.",
                    )
                prev_out = float(step.qty_out)

        if float(batch.current_qty) - float(batch.initial_qty) > EPS:
            _add_finding(
                findings,
                severity="high",
                check="batch_current_not_exceed_initial",
                table="batches",
                record_ref=ref,
                message=(
                    f"current_qty exceeds initial_qty ({_fmt_float(batch.current_qty)} > {_fmt_float(batch.initial_qty)})."
                ),
                suggested_fix="Review process-step output and losses for overproduction anomalies.",
            )


def _validate_commercial(db, findings: list[Finding], checked: dict[str, int]) -> None:
    orders = db.scalars(select(CommercialOrder)).all()
    invoices = db.scalars(select(CommercialInvoice)).all()
    checked["commercial_orders"] = len(orders)
    checked["commercial_invoices"] = len(invoices)

    order_lines = db.scalars(select(CommercialOrderLine)).all()
    invoice_lines = db.scalars(select(CommercialInvoiceLine)).all()
    checked["commercial_order_lines"] = len(order_lines)
    checked["commercial_invoice_lines"] = len(invoice_lines)

    order_lines_by_order: dict[Any, list[CommercialOrderLine]] = {}
    for line in order_lines:
        order_lines_by_order.setdefault(line.order_id, []).append(line)

    invoice_lines_by_invoice: dict[Any, list[CommercialInvoiceLine]] = {}
    for line in invoice_lines:
        invoice_lines_by_invoice.setdefault(line.invoice_id, []).append(line)

    invoice_by_order = {inv.order_id: inv for inv in invoices}

    for order in orders:
        ref = f"order:{order.id}"
        lines = order_lines_by_order.get(order.id, [])
        if not lines:
            _add_finding(
                findings,
                severity="high",
                check="order_has_lines",
                table="commercial_orders,commercial_order_lines",
                record_ref=ref,
                message="Order has no lines.",
                suggested_fix="Add at least one commercial_order_line or remove invalid order.",
            )
            continue

        sum_lines = float(sum(float(line.line_total_fcfa or 0.0) for line in lines))
        if not _is_close(float(order.subtotal_fcfa), sum_lines, tol=1.0):
            _add_finding(
                findings,
                severity="high",
                check="order_subtotal_matches_lines",
                table="commercial_orders,commercial_order_lines",
                record_ref=ref,
                message=(
                    f"subtotal_fcfa ({_fmt_float(order.subtotal_fcfa)}) != sum(line_total_fcfa) ({_fmt_float(sum_lines)})."
                ),
                suggested_fix="Recompute order subtotal from lines.",
            )

        expected_total = float(order.subtotal_fcfa) + float(order.tax_amount_fcfa)
        if not _is_close(float(order.total_amount_fcfa), expected_total, tol=1.0):
            _add_finding(
                findings,
                severity="high",
                check="order_total_matches_subtotal_plus_tax",
                table="commercial_orders",
                record_ref=ref,
                message=(
                    f"total_amount_fcfa ({_fmt_float(order.total_amount_fcfa)}) != subtotal+tax ({_fmt_float(expected_total)})."
                ),
                suggested_fix="Recompute order tax and total values.",
            )

        # Status/timestamp coherence
        if order.status == CommercialOrderStatus.DELIVERED and order.delivered_at is None:
            _add_finding(
                findings,
                severity="medium",
                check="order_status_timestamp_coherence",
                table="commercial_orders",
                record_ref=ref,
                message="Order status is delivered but delivered_at is null.",
                suggested_fix="Populate delivered_at when status transitions to delivered.",
            )
        if order.status == CommercialOrderStatus.PAID and order.paid_at is None:
            _add_finding(
                findings,
                severity="medium",
                check="order_status_timestamp_coherence",
                table="commercial_orders",
                record_ref=ref,
                message="Order status is paid but paid_at is null.",
                suggested_fix="Populate paid_at when status transitions to paid.",
            )
        if order.status == CommercialOrderStatus.REFUSED and order.refused_at is None:
            _add_finding(
                findings,
                severity="medium",
                check="order_status_timestamp_coherence",
                table="commercial_orders",
                record_ref=ref,
                message="Order status is refused but refused_at is null.",
                suggested_fix="Populate refused_at when status transitions to refused.",
            )

        inv = invoice_by_order.get(order.id)
        if order.status == CommercialOrderStatus.PAID and inv is not None and inv.status != InvoiceStatus.PAID:
            _add_finding(
                findings,
                severity="high",
                check="order_invoice_status_alignment",
                table="commercial_orders,commercial_invoices",
                record_ref=ref,
                message="Order is paid but linked invoice is not marked as paid.",
                suggested_fix="Synchronize invoice status with paid order status transition.",
            )

    for invoice in invoices:
        ref = f"invoice:{invoice.id}"
        lines = invoice_lines_by_invoice.get(invoice.id, [])
        if not lines:
            _add_finding(
                findings,
                severity="high",
                check="invoice_has_lines",
                table="commercial_invoices,commercial_invoice_lines",
                record_ref=ref,
                message="Invoice has no lines.",
                suggested_fix="Add invoice lines or remove orphan invoice.",
            )
            continue

        sum_lines = float(sum(float(line.line_total_fcfa or 0.0) for line in lines))
        if not _is_close(float(invoice.subtotal_fcfa), sum_lines, tol=1.0):
            _add_finding(
                findings,
                severity="high",
                check="invoice_subtotal_matches_lines",
                table="commercial_invoices,commercial_invoice_lines",
                record_ref=ref,
                message=(
                    f"subtotal_fcfa ({_fmt_float(invoice.subtotal_fcfa)}) != sum(line_total_fcfa) ({_fmt_float(sum_lines)})."
                ),
                suggested_fix="Recompute invoice subtotal from invoice lines.",
            )

        expected_total = float(invoice.subtotal_fcfa) + float(invoice.tax_amount_fcfa)
        if not _is_close(float(invoice.total_amount_fcfa), expected_total, tol=1.0):
            _add_finding(
                findings,
                severity="high",
                check="invoice_total_matches_subtotal_plus_tax",
                table="commercial_invoices",
                record_ref=ref,
                message=(
                    f"total_amount_fcfa ({_fmt_float(invoice.total_amount_fcfa)}) != subtotal+tax ({_fmt_float(expected_total)})."
                ),
                suggested_fix="Recompute invoice tax and total values.",
            )

        if invoice.status == InvoiceStatus.PAID and invoice.paid_at is None:
            _add_finding(
                findings,
                severity="medium",
                check="invoice_status_timestamp_coherence",
                table="commercial_invoices",
                record_ref=ref,
                message="Invoice status is paid but paid_at is null.",
                suggested_fix="Populate paid_at when invoice status transitions to paid.",
            )


def _validate_finance(db, findings: list[Finding], checked: dict[str, int]) -> None:
    charges = db.scalars(select(GlobalCharge)).all()
    advances = db.scalars(select(FarmerAdvance)).all()
    treasury = db.scalars(select(TreasuryTransaction)).all()

    checked["global_charges"] = len(charges)
    checked["farmer_advances"] = len(advances)
    checked["treasury_transactions"] = len(treasury)

    for charge in charges:
        if float(charge.amount_fcfa) < -EPS:
            _add_finding(
                findings,
                severity="high",
                check="charge_amount_non_negative",
                table="global_charges",
                record_ref=f"charge:{charge.id}",
                message=f"Negative charge amount ({_fmt_float(charge.amount_fcfa)}).",
                suggested_fix="Correct charge amount sign and category mapping.",
            )

    for adv in advances:
        if float(adv.amount_fcfa) < -EPS:
            _add_finding(
                findings,
                severity="high",
                check="advance_amount_non_negative",
                table="farmer_advances",
                record_ref=f"advance:{adv.id}",
                message=f"Negative advance amount ({_fmt_float(adv.amount_fcfa)}).",
                suggested_fix="Correct farmer advance amount sign.",
            )

    for trx in treasury:
        if float(trx.amount_fcfa) < -EPS:
            _add_finding(
                findings,
                severity="high",
                check="treasury_amount_non_negative",
                table="treasury_transactions",
                record_ref=f"trx:{trx.id}",
                message=f"Negative treasury amount ({_fmt_float(trx.amount_fcfa)}).",
                suggested_fix="Use transaction type field for sign semantics; keep amount absolute.",
            )


def _reconcile_operational_snapshots(db) -> dict[str, int]:
    fixes = {
        "batch_current_qty_synced": 0,
        "stock_reserved_synced": 0,
        "stock_available_synced": 0,
        "stock_total_raised_to_reserved": 0,
    }

    batches = db.scalars(select(Batch)).all()
    for batch in batches:
        steps = db.scalars(
            select(ProcessStep)
            .where(ProcessStep.batch_id == batch.id)
            .order_by(ProcessStep.sequence_order.asc(), ProcessStep.date.asc(), ProcessStep.created_at.asc(), ProcessStep.id.asc())
        ).all()
        expected_current = float(batch.initial_qty) if not steps else float(steps[-1].qty_out)
        if not _is_close(float(batch.current_qty), expected_current):
            batch.current_qty = round(expected_current, 2)
            fixes["batch_current_qty_synced"] += 1

    active_rows = db.execute(
        select(Batch.product_id, func.coalesce(func.sum(Batch.initial_qty), 0.0))
        .where(Batch.status.in_([BatchStatus.CREATED, BatchStatus.IN_PROGRESS]))
        .group_by(Batch.product_id)
    ).all()
    reserved_by_product = {row[0]: float(row[1] or 0.0) for row in active_rows}

    stocks = db.scalars(select(Stock)).all()
    for stock in stocks:
        expected_reserved = round(float(reserved_by_product.get(stock.product_id, 0.0)), 2)
        if not _is_close(float(stock.reserved_in_lots_kg), expected_reserved):
            stock.reserved_in_lots_kg = expected_reserved
            fixes["stock_reserved_synced"] += 1
        if float(stock.total_stock_kg) + EPS < float(stock.reserved_in_lots_kg):
            stock.total_stock_kg = round(float(stock.reserved_in_lots_kg), 2)
            fixes["stock_total_raised_to_reserved"] += 1
        expected_available = round(max(float(stock.total_stock_kg) - float(stock.reserved_in_lots_kg), 0.0), 2)
        if not _is_close(float(stock.quantity), expected_available):
            stock.quantity = expected_available
            fixes["stock_available_synced"] += 1

    db.commit()
    return fixes


def _build_report(
    checked: dict[str, int],
    findings: list[Finding],
    fixes: dict[str, int] | None = None,
) -> str:
    total_checked = sum(int(v) for v in checked.values())
    by_severity: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for finding in findings:
        by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1

    penalty = sum(_severity_weight(item.severity) for item in findings)
    integrity_score = max(0.0, 100.0 - (float(penalty) / max(float(total_checked), 1.0)) * 100.0)

    lines: list[str] = [
        "# Demo Data Integrity Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Checked Tables",
    ]

    for table_name, count in sorted(checked.items(), key=lambda x: x[0]):
        lines.append(f"- {table_name}: {count} records checked")

    lines.extend(
        [
            "",
            "## Inconsistency Summary",
            f"- Total inconsistencies: {len(findings)}",
            f"- Critical: {by_severity.get('critical', 0)}",
            f"- High: {by_severity.get('high', 0)}",
            f"- Medium: {by_severity.get('medium', 0)}",
            f"- Low: {by_severity.get('low', 0)}",
            f"- Data integrity score: {integrity_score:.2f}/100",
            "",
            "## Findings",
        ]
    )

    if fixes is not None:
        lines.extend(
            [
                "",
                "## Applied Reconciliation Fixes",
                f"- batch_current_qty_synced: {fixes.get('batch_current_qty_synced', 0)}",
                f"- stock_reserved_synced: {fixes.get('stock_reserved_synced', 0)}",
                f"- stock_available_synced: {fixes.get('stock_available_synced', 0)}",
                f"- stock_total_raised_to_reserved: {fixes.get('stock_total_raised_to_reserved', 0)}",
            ]
        )

    if not findings:
        lines.append("- No inconsistencies found.")
    else:
        for idx, finding in enumerate(findings, start=1):
            lines.extend(
                [
                    f"### {idx}. [{finding.severity.upper()}] {finding.check}",
                    f"- Table(s): {finding.table}",
                    f"- Record: {finding.record_ref}",
                    f"- Issue: {finding.message}",
                    f"- Suggested fix: {finding.suggested_fix}",
                    "",
                ]
            )

    final_grade = "PASS"
    if by_severity.get("critical", 0) > 0:
        final_grade = "FAIL"
    elif integrity_score < 85.0:
        final_grade = "WARNING"

    lines.extend(
        [
            "## Final Assessment",
            f"- Final grade: {final_grade}",
            "- Acceptance criterion: no critical data inconsistency.",
            "",
            "## Rerun",
            "```bash",
            "./.venv/bin/python backend/scripts/validate_demo_data_integrity.py",
            "./.venv/bin/python backend/scripts/validate_demo_data_integrity.py --fix",
            "```",
        ]
    )

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate demo operational data integrity.")
    parser.add_argument("--fix", action="store_true", help="Apply safe snapshot reconciliations before validation.")
    args = parser.parse_args()

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    findings: list[Finding] = []
    checked: dict[str, int] = {}
    fixes: dict[str, int] | None = None

    try:
        if args.fix:
            fixes = _reconcile_operational_snapshots(db)
        _validate_stocks_and_reservations(db, findings, checked)
        _validate_batches_and_process(db, findings, checked)
        _validate_commercial(db, findings, checked)
        _validate_finance(db, findings, checked)

        report = _build_report(checked, findings, fixes=fixes)
        REPORT_PATH.write_text(report, encoding="utf-8")
        print(f"Saved {REPORT_PATH}")
        print(f"Total findings: {len(findings)}")
        if fixes is not None:
            print(f"Applied fixes: {fixes}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
