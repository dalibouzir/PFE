from __future__ import annotations

import argparse
from pathlib import Path
import sys

from sqlalchemy import delete, select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.models.batch import Batch
from app.models.commercial_catalog_product import CommercialCatalogProduct
from app.models.commercial_invoice import CommercialInvoice, CommercialInvoiceLine
from app.models.commercial_order import CommercialOrder, CommercialOrderLine
from app.models.cooperative import Cooperative
from app.models.farmer_advance import FarmerAdvance
from app.models.field import Field
from app.models.global_charge import GlobalCharge
from app.models.input import Input
from app.models.member import Member
from app.models.parcel import Parcel
from app.models.pre_harvest_step import PreHarvestStep
from app.models.process_step import ProcessStep
from app.models.recommendation import Recommendation
from app.models.stock import Stock
from app.models.stock_movement import StockMovement
from app.models.treasury_transaction import TreasuryTransaction


def reset_cooperative(name: str) -> dict[str, int]:
    with SessionLocal() as session:
        coop = session.scalar(select(Cooperative).where(Cooperative.name == name))
        if coop is None:
            raise RuntimeError(f"Cooperative not found: {name}")
        coop_id = coop.id

        order_ids = session.scalars(select(CommercialOrder.id).where(CommercialOrder.cooperative_id == coop_id)).all()
        invoice_ids = session.scalars(select(CommercialInvoice.id).where(CommercialInvoice.cooperative_id == coop_id)).all()

        counters: dict[str, int] = {}

        if invoice_ids:
            counters["commercial_invoice_lines"] = session.execute(
                delete(CommercialInvoiceLine).where(CommercialInvoiceLine.invoice_id.in_(invoice_ids))
            ).rowcount or 0
        if order_ids:
            counters["commercial_order_lines"] = session.execute(
                delete(CommercialOrderLine).where(CommercialOrderLine.order_id.in_(order_ids))
            ).rowcount or 0

        counters["recommendations"] = session.execute(
            delete(Recommendation).where(Recommendation.batch_id.in_(select(Batch.id).where(Batch.cooperative_id == coop_id)))
        ).rowcount or 0
        counters["process_steps"] = session.execute(
            delete(ProcessStep).where(ProcessStep.batch_id.in_(select(Batch.id).where(Batch.cooperative_id == coop_id)))
        ).rowcount or 0
        counters["batches"] = session.execute(delete(Batch).where(Batch.cooperative_id == coop_id)).rowcount or 0

        counters["stock_movements"] = session.execute(delete(StockMovement).where(StockMovement.cooperative_id == coop_id)).rowcount or 0
        counters["stocks"] = session.execute(delete(Stock).where(Stock.cooperative_id == coop_id)).rowcount or 0
        counters["inputs"] = session.execute(delete(Input).where(Input.cooperative_id == coop_id)).rowcount or 0

        counters["commercial_invoices"] = session.execute(delete(CommercialInvoice).where(CommercialInvoice.cooperative_id == coop_id)).rowcount or 0
        counters["commercial_orders"] = session.execute(delete(CommercialOrder).where(CommercialOrder.cooperative_id == coop_id)).rowcount or 0
        counters["commercial_catalog_products"] = session.execute(
            delete(CommercialCatalogProduct).where(CommercialCatalogProduct.cooperative_id == coop_id)
        ).rowcount or 0

        counters["farmer_advances"] = session.execute(delete(FarmerAdvance).where(FarmerAdvance.cooperative_id == coop_id)).rowcount or 0
        counters["treasury_transactions"] = session.execute(
            delete(TreasuryTransaction).where(TreasuryTransaction.cooperative_id == coop_id)
        ).rowcount or 0
        counters["global_charges"] = session.execute(delete(GlobalCharge).where(GlobalCharge.cooperative_id == coop_id)).rowcount or 0
        counters["pre_harvest_steps"] = session.execute(delete(PreHarvestStep).where(PreHarvestStep.cooperative_id == coop_id)).rowcount or 0

        counters["parcels"] = session.execute(delete(Parcel).where(Parcel.cooperative_id == coop_id)).rowcount or 0
        counters["fields"] = session.execute(delete(Field).where(Field.cooperative_id == coop_id)).rowcount or 0
        counters["members"] = session.execute(delete(Member).where(Member.cooperative_id == coop_id)).rowcount or 0

        session.commit()
        counters["cooperative_id"] = str(coop_id)  # type: ignore[assignment]
        return counters


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset operational data for one cooperative.")
    parser.add_argument("--cooperative-name", required=True)
    args = parser.parse_args()
    result = reset_cooperative(args.cooperative_name)
    print(result)


if __name__ == "__main__":
    main()
