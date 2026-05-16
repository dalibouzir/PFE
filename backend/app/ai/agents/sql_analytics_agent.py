from __future__ import annotations

import re
import time
import unicodedata
from datetime import date
from typing import Any

from app.ai.agents.base_agent import BaseAgent
from app.ai.schemas.agent_schemas import AgentContext, AgentResult
from app.ai.tools.sql_tools import SQLTools


class SQLAnalyticsAgent(BaseAgent):
    name = "SQLAnalyticsAgent"
    description = "Retrieves structured cooperative operational data via controlled SQL tools."

    def __init__(self, sql_tools: SQLTools):
        self.sql_tools = sql_tools

    async def run(self, query: str, context: AgentContext) -> AgentResult:
        start = time.perf_counter()
        entities = context.detected_entities or {}
        product = _pick_first(entities.get("product"))
        stage = _pick_first(entities.get("stage"))
        batch_ref = entities.get("batch_ref")
        lowered = query.lower()
        normalized = _normalize_text(query)
        reset_lot_context = any(
            token in normalized
            for token in ("oublie ce lot", "oublier ce lot", "maintenant oublie", "passons a", "changeons de sujet")
        )
        date_range = entities.get("date_range")
        effective_date_range = date_range
        if any(token in lowered for token in ("aujourd'hui", "aujourd’hui", "aujourdhui", "today")):
            today = date.today().isoformat()
            effective_date_range = [today, today]
        scope = entities.get("scope", "global")
        module = entities.get("module", "global")
        member_name = entities.get("member_name")

        asks_member_ranking = any(
            token in normalized
            for token in (
                "quel membre a livré le plus",
                "quel membre a livre le plus",
                "classe les membres",
                "classement des membres",
                "top membre",
                "top members",
                "top producteurs",
                "premier",
                "premiers",
                "top 3",
                "top 5",
            )
        )
        if not asks_member_ranking and str(entities.get("module") or "") == "members":
            if any(token in normalized for token in ("premier", "premiers", "suivant", "encore")):
                asks_member_ranking = True
        asks_member_value = any(token in normalized for token in ("plus de valeur", "plus de cout", "genere le plus de valeur"))
        asks_parcel_count = any(token in normalized for token in ("combien", "nombre", "total")) and any(
            token in normalized for token in ("parcelle", "parcelles", "parcel")
        )
        asks_cooperative_summary = module == "cooperative_summary" or (
            any(token in normalized for token in ("cooperative",))
            and any(token in normalized for token in ("resume", "synthese", "apercu"))
        )
        asks_stage_comparison = "compare" in normalized and any(token in normalized for token in ("sechage", "drying")) and any(
            token in normalized for token in ("tri", "sorting")
        )
        warnings: list[str] = []
        payload: dict[str, Any] = {}
        payload["module_capabilities"] = self.sql_tools.get_module_capabilities()
        payload["detected_module"] = module
        payload["query_text"] = query
        if batch_ref:
            payload["requested_batch_ref"] = batch_ref
        sources: list[dict[str, Any]] = []

        # Deterministic high-precision operations for defense-critical queries.
        op = _detect_deterministic_operation(normalized)
        if op:
            product_for_query = product or _detect_product_from_text(normalized)
            payload["query_operation"] = op
            if op == "avg_paid_invoices_current_quarter":
                r = self.sql_tools.avg_paid_invoices_current_quarter()
                payload["avg_paid_invoices_current_quarter"] = r.get("items", [])
            elif op == "top_customer_by_orders":
                r = self.sql_tools.top_customer_by_orders()
                payload["top_customer_by_orders"] = r.get("items", [])
            elif op == "month_vs_month_charges":
                r = self.sql_tools.month_vs_month_charges()
                payload["month_vs_month_charges"] = r.get("items", [])
            elif op == "lowest_nonzero_member_contributor":
                r = self.sql_tools.lowest_nonzero_member_contributor()
                payload["lowest_nonzero_member_contributor"] = r.get("items", [])
            elif op == "largest_parcel_by_product":
                r = self.sql_tools.largest_parcel_by_product(product=product_for_query or "")
                payload["largest_parcel_by_product"] = r.get("items", [])
            elif op == "top_grade_by_volume":
                days = _extract_days(lowered, default_days=90)
                r = self.sql_tools.top_grade_by_volume(days=days)
                payload["top_grade_by_volume"] = r.get("items", [])
            elif op == "top_collection_days":
                days = 180 if "6 mois" in lowered else _extract_days(lowered, default_days=180)
                r = self.sql_tools.top_collection_days(days=days, limit=3)
                payload["top_collection_days"] = r.get("items", [])
            elif op == "available_stock_gap":
                r = self.sql_tools.available_stock_gap(product=product_for_query or "")
                payload["available_stock_gap"] = r.get("items", [])
            elif op == "oldest_open_lot":
                r = self.sql_tools.oldest_open_lot()
                payload["oldest_open_lot"] = r.get("items", [])
            elif op == "process_stage_loss_ranking":
                days = _extract_days(lowered, default_days=30)
                r = self.sql_tools.process_stage_loss_ranking(days=days)
                payload["process_stage_loss_ranking"] = r.get("items", [])
            else:
                r = {"items": [], "sources": [], "warnings": []}
            sources.extend(r.get("sources", []))
            warnings.extend(r.get("warnings", []))
            answer_part = _build_sql_answer(payload)
            confidence = 0.9 if r.get("items") else 0.4
            return AgentResult(
                agent_name=self.name,
                route=context.route,
                answer_part=answer_part,
                data=payload,
                sources=sources,
                confidence=confidence,
                warnings=sorted(set(warnings)),
                execution_time_ms=int((time.perf_counter() - start) * 1000),
            )

        # Pre-harvest and parcel queries
        if scope == "pre_harvest" or any(token in normalized for token in ("pre-recolte", "pre-harvest", "parcelle", "parcelles", "preharvest")):
            if asks_parcel_count:
                parcels = self.sql_tools.get_parcels_list(product=product)
                payload["parcels_list"] = parcels.get("items", [])
                payload["parcel_count"] = len(payload["parcels_list"])
                sources.extend(parcels.get("sources", []))
                warnings.extend(parcels.get("warnings", []))
            if any(token in normalized for token in ("liste les parcelles", "parcelles enregistrees", "liste des parcelles")):
                parcels = self.sql_tools.get_parcels_list(product=product)
                payload["parcels_list"] = parcels.get("items", [])
                sources.extend(parcels.get("sources", []))
                warnings.extend(parcels.get("warnings", []))
            if any(token in normalized for token in ("parcelle", "parcelles", "parcel")) or "action" in normalized or "necessite" in normalized:
                # Get parcel status
                parcel_status = self.sql_tools.preharvest.get_parcel_preharvest_status(product=product)
                payload["parcel_status"] = parcel_status.get("data", [])
                sources.extend(parcel_status.get("sources", []))
                warnings.extend(parcel_status.get("warnings", []))
                
                parcel_missing = self.sql_tools.preharvest.get_parcels_missing_data()
                payload["parcels_missing_data"] = parcel_missing.get("data", [])
                sources.extend(parcel_missing.get("sources", []))
                warnings.extend(parcel_missing.get("warnings", []))
            else:
                # General pre-harvest status
                preharvest_status = self.sql_tools.preharvest.get_parcel_preharvest_status(product=product)
                payload["preharvest_status"] = preharvest_status.get("data", [])
                sources.extend(preharvest_status.get("sources", []))
                warnings.extend(preharvest_status.get("warnings", []))

        if asks_cooperative_summary:
            coop = self.sql_tools.get_cooperative_overview()
            payload["cooperative_overview"] = coop.get("items", [])
            sources.extend(coop.get("sources", []))
            warnings.extend(coop.get("warnings", []))

        if _contains_stock_keyword(normalized):
            stock = self.sql_tools.get_current_stock(product=product)
            payload["current_stock"] = stock.get("items", [])
            sources.extend(stock.get("sources", []))
            warnings.extend(stock.get("warnings", []))

        if (module == "members" or any(token in normalized for token in ("membre", "membres", "member", "farmer", "producteur", "producteurs"))) and not asks_member_ranking:
            members = self.sql_tools.get_members_list(member_name=member_name)
            payload["members_list"] = members.get("items", [])
            sources.extend(members.get("sources", []))
            warnings.extend(members.get("warnings", []))

        if asks_member_ranking:
            top_farmers = self.sql_tools.get_top_farmers(product=product, date_range=effective_date_range)
            payload["top_farmers"] = top_farmers.get("items", [])
            sources.extend(top_farmers.get("sources", []))
            warnings.extend(top_farmers.get("warnings", []))

        if module == "member_value" or asks_member_value or (
            any(token in normalized for token in ("membre", "membres", "producteur", "producteurs"))
            and any(token in normalized for token in ("valeur", "cout"))
        ):
            payload["member_value_module_available"] = self.sql_tools.module_available("global_charges")
            top_members_by_cost = self.sql_tools.get_top_members_by_cost(date_range=date_range)
            payload["top_members_by_cost"] = top_members_by_cost.get("items", [])
            sources.extend(top_members_by_cost.get("sources", []))
            warnings.extend(top_members_by_cost.get("warnings", []))

        if any(token in normalized for token in ("collect", "collecte", "input")):
            collections = self.sql_tools.get_collections_summary(product=product, date_range=effective_date_range)
            payload["collections_summary"] = collections.get("items", [])
            sources.extend(collections.get("sources", []))
            warnings.extend(collections.get("warnings", []))

        if module == "invoices" or any(token in normalized for token in ("facture", "factures", "invoice", "invoices")):
            payload["invoices_module_available"] = self.sql_tools.module_available("commercial_invoices")
            invoices = self.sql_tools.get_invoices_summary()
            payload["invoices_summary"] = invoices.get("items", [])
            sources.extend(invoices.get("sources", []))
            warnings.extend(invoices.get("warnings", []))

        if module == "commercial" or any(
            token in normalized for token in ("commande", "commandes", "vente", "ventes", "commercialisation", "commercial")
        ):
            payload["commercial_module_available"] = self.sql_tools.module_available("commercial_orders")
            orders = self.sql_tools.get_commercial_orders_summary()
            totals = self.sql_tools.get_commercial_totals()
            payload["commercial_orders"] = orders.get("items", [])
            payload["commercial_totals"] = totals.get("items", [])
            sources.extend(orders.get("sources", []))
            sources.extend(totals.get("sources", []))
            warnings.extend(orders.get("warnings", []))
            warnings.extend(totals.get("warnings", []))

        if module == "finance" or any(
            token in normalized for token in ("finance", "tresorerie", "charge", "charges", "depense")
        ):
            payload["finance_module_available"] = self.sql_tools.module_available("treasury_transactions") or self.sql_tools.module_available("global_charges")
            finance = self.sql_tools.get_finance_expenses()
            payload["finance_expenses"] = finance.get("items", [])
            sources.extend(finance.get("sources", []))
            warnings.extend(finance.get("warnings", []))

        if (batch_ref or any(token in normalized for token in ("lot", "batch"))) and not reset_lot_context:
            batch = self.sql_tools.get_batch_summary(batch_ref=batch_ref)
            payload["batch_summary"] = batch.get("items", [])
            sources.extend(batch.get("sources", []))
            warnings.extend(batch.get("warnings", []))
            if any(token in normalized for token in ("en cours", "in progress")):
                payload["in_progress_lots"] = [
                    row for row in (batch.get("items", []) or []) if str(row.get("status", "")).lower() == "in_progress"
                ]
            if any(token in normalized for token in ("efficacite faible", "faible efficacite")):
                payload["low_efficiency_lots"] = [
                    row for row in (batch.get("items", []) or []) if float(row.get("efficiency_pct", 0.0) or 0.0) < 85.0
                ]
            if any(
                token in normalized
                for token in (
                    "plus de pertes",
                    "pertes les plus élevées",
                    "pertes les plus elevees",
                    "plus élevées",
                    "plus elevees",
                    "most loss",
                    "highest loss",
                    "plus perte",
                    "risque",
                    "risk",
                )
            ):
                high_risk_lots = self.sql_tools.get_high_risk_lots()
                payload["high_risk_lots"] = high_risk_lots.get("items", [])
                sources.extend(high_risk_lots.get("sources", []))
                warnings.extend(high_risk_lots.get("warnings", []))
                payload["top_loss_batches"] = sorted(
                    batch.get("items", []),
                    key=lambda item: float(item.get("loss_pct", 0.0) or 0.0),
                    reverse=True,
                )[:5]

        if any(token in normalized for token in ("perte", "loss", "efficacit", "efficiency", "sechage", "tri", "drying", "sorting", "emballage", "packaging")):
            losses = self.sql_tools.get_process_step_losses(
                batch_ref=batch_ref,
                stage=stage,
                product=product,
                date_range=effective_date_range,
            )
            payload["process_step_losses"] = losses.get("items", [])
            sources.extend(losses.get("sources", []))
            warnings.extend(losses.get("warnings", []))

            stage_eff = self.sql_tools.get_stage_efficiency_summary(product=product, date_range=effective_date_range)
            payload["stage_efficiency_summary"] = stage_eff.get("items", [])
            sources.extend(stage_eff.get("sources", []))
            warnings.extend(stage_eff.get("warnings", []))
            if any(token in normalized for token in ("efficacite faible", "faible efficacite")):
                if not payload.get("low_efficiency_lots"):
                    batch_all = self.sql_tools.get_batch_summary(batch_ref=None)
                    payload["low_efficiency_lots"] = [
                        row for row in (batch_all.get("items", []) or []) if float(row.get("efficiency_pct", 0.0) or 0.0) < 85.0
                    ]
                    sources.extend(batch_all.get("sources", []))
                    warnings.extend(batch_all.get("warnings", []))
            if asks_stage_comparison:
                stage_rows = payload.get("stage_efficiency_summary", [])
                stage_map: dict[str, dict[str, Any]] = {}
                for row in stage_rows:
                    stage_name = str(row.get("stage") or "").lower().strip()
                    stage_map[stage_name] = row
                drying = stage_map.get("drying") or stage_map.get("séchage") or stage_map.get("sechage")
                sorting = stage_map.get("sorting") or stage_map.get("tri")
                comparison_rows = []
                if drying:
                    comparison_rows.append({"stage": "drying", "stage_label": "Séchage", "avg_loss_pct": float(drying.get("avg_loss_pct", 0.0) or 0.0)})
                if sorting:
                    comparison_rows.append({"stage": "sorting", "stage_label": "Tri", "avg_loss_pct": float(sorting.get("avg_loss_pct", 0.0) or 0.0)})
                payload["stage_loss_comparison"] = comparison_rows

        if "bilan" in normalized or "material balance" in normalized or "matiere" in normalized:
            balance = self.sql_tools.get_material_balance(batch_ref=batch_ref, product=product)
            payload["material_balance"] = balance.get("items", [])
            sources.extend(balance.get("sources", []))
            warnings.extend(balance.get("warnings", []))

        contains_member_top_intent = bool(
            re.search(r"\b(top|classement|classer|plus\s+gros)\b", normalized)
            or (
                re.search(r"\bmeilleur(?:e|es)?\b", normalized)
                and re.search(r"\b(membre|producteur|farmer)s?\b", normalized)
            )
        )
        if contains_member_top_intent and not payload.get("top_farmers"):
            top_farmers = self.sql_tools.get_top_farmers(product=product, date_range=effective_date_range)
            payload["top_farmers"] = top_farmers.get("items", [])
            sources.extend(top_farmers.get("sources", []))
            warnings.extend(top_farmers.get("warnings", []))

        if "seuil" in normalized or "alert" in normalized:
            low_stock = self.sql_tools.get_low_stock_alerts()
            payload["low_stock_alerts"] = low_stock.get("items", [])
            sources.extend(low_stock.get("sources", []))
            warnings.extend(low_stock.get("warnings", []))

        module_specific = module in {"members", "member_value", "collections", "stocks", "invoices", "commercial", "finance", "pre_harvest"}
        operational_keys = [key for key in payload.keys() if key not in {"module_capabilities", "detected_module", "query_text", "requested_batch_ref"}]
        has_operational_data = any(payload.get(key) for key in operational_keys)

        if not has_operational_data and not module_specific:
            # Default operational pack for broad SQL/follow-up queries.
            batch = self.sql_tools.get_batch_summary(batch_ref=batch_ref)
            losses = self.sql_tools.get_process_step_losses(batch_ref=batch_ref, stage=stage, product=product, date_range=effective_date_range)
            payload["batch_summary"] = batch.get("items", [])
            payload["process_step_losses"] = losses.get("items", [])
            if not batch_ref and module in {"post_harvest", "material_balance"}:
                high_risk_lots = self.sql_tools.get_high_risk_lots()
                payload["high_risk_lots"] = high_risk_lots.get("items", [])
                sources.extend(high_risk_lots.get("sources", []))
                warnings.extend(high_risk_lots.get("warnings", []))
            sources.extend(batch.get("sources", []))
            sources.extend(losses.get("sources", []))
            warnings.extend(batch.get("warnings", []))
            warnings.extend(losses.get("warnings", []))

        if all(not value for key, value in payload.items() if key not in {"detected_module", "query_text", "requested_batch_ref"}):
            warnings.append("SQL_DATA_INCOMPLETE")
        payload = _apply_post_aggregation_checks(payload)

        answer_part = _build_sql_answer(payload)
        confidence = 0.88 if "SQL_DATA_INCOMPLETE" not in warnings and "NO_SQL_DATA" not in warnings else 0.48

        return AgentResult(
            agent_name=self.name,
            route=context.route,
            answer_part=answer_part,
            data=payload,
            sources=sources,
            confidence=confidence,
            warnings=sorted(set(warnings)),
            execution_time_ms=int((time.perf_counter() - start) * 1000),
        )


def _pick_first(value):
    if isinstance(value, list) and value:
        return value[0]
    if isinstance(value, str):
        return value
    return None


def _extract_days(text: str, default_days: int) -> int:
    m = re.search(r"(\d+)\s*jour", text)
    if m:
        return max(1, int(m.group(1)))
    m = re.search(r"(\d+)\s*mois", text)
    if m:
        return max(1, int(m.group(1)) * 30)
    return default_days


def _detect_deterministic_operation(normalized: str) -> str | None:
    if (
        "trimestre" in normalized
        and re.search(r"\bmoyenn?e?s?\b", normalized)
        and re.search(r"\bfactur\w*\b", normalized)
        and re.search(r"\b(pay\w*|regl\w*)\b", normalized)
    ):
        return "avg_paid_invoices_current_quarter"
    if "client" in normalized and ("plus gros cumul" in normalized or "plus de commandes" in normalized):
        return "top_customer_by_orders"
    if "charges globales" in normalized and (
        "vs" in normalized
        or "mois dernier" in normalized
        or "mois precedent" in normalized
        or ("compare" in normalized and "ce mois" in normalized)
    ):
        return "month_vs_month_charges"
    if "plus petit contributeur" in normalized and "zero" in normalized:
        return "lowest_nonzero_member_contributor"
    if "parcelle" in normalized and "plus grande" in normalized:
        return "largest_parcel_by_product"
    if "grade" in normalized and (
        "pese le plus" in normalized
        or "plus en volume" in normalized
        or ("domine" in normalized and ("volume" in normalized or "collect" in normalized))
    ):
        return "top_grade_by_volume"
    if "collecte" in normalized and re.search(r"\b(top\s*\d*|plus fort|plus forts|plus fortes)\b", normalized) and "jour" in normalized:
        return "top_collection_days"
    if "disponible net" in normalized and "seuil" in normalized:
        return "available_stock_gap"
    if ("lots encore ouverts" in normalized or "lots ouverts" in normalized) and "plus ancien" in normalized:
        return "oldest_open_lot"
    if "etape" in normalized and re.search(r"plus\s+de\s+pertes?|plus\s+de\s+perte", normalized):
        return "process_stage_loss_ranking"
    return None


def _normalize_text(value: str) -> str:
    raw = str(value or "").lower()
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return " ".join(raw.split())


def _contains_stock_keyword(normalized: str) -> bool:
    return bool(re.search(r"\bstock(s)?\b", normalized))


def _detect_product_from_text(normalized: str) -> str | None:
    if "arachide" in normalized or "peanut" in normalized:
        return "arachide"
    if "mangue" in normalized or "mango" in normalized:
        return "mangue"
    if "millet" in normalized or re.search(r"\bmil\b", normalized):
        return "mil"
    if "bissap" in normalized:
        return "bissap"
    return None


def _build_sql_answer(payload: dict[str, Any]) -> str:
    if payload.get("avg_paid_invoices_current_quarter") is not None:
        rows = payload.get("avg_paid_invoices_current_quarter", [])
        if rows:
            return f"Montant moyen des factures payées ce trimestre: {float(rows[0].get('avg_paid_invoice_fcfa', 0.0)):.0f} FCFA."
        return "Donnée non disponible pour cette requête précise."
    if payload.get("top_customer_by_orders") is not None:
        rows = payload.get("top_customer_by_orders", [])
        if rows:
            return f"Client top commandes: {rows[0].get('customer_name')} avec {float(rows[0].get('total_amount_fcfa', 0.0)):.0f} FCFA."
        return "Donnée non disponible pour cette requête précise."
    if payload.get("month_vs_month_charges") is not None:
        rows = payload.get("month_vs_month_charges", [])
        if rows:
            row = rows[0]
            return f"Charges: mois en cours {float(row.get('current_month_fcfa', 0.0)):.0f} FCFA vs mois dernier {float(row.get('previous_month_fcfa', 0.0)):.0f} FCFA."
        return "Donnée non disponible pour cette requête précise."
    if payload.get("lowest_nonzero_member_contributor") is not None:
        rows = payload.get("lowest_nonzero_member_contributor", [])
        if rows:
            return f"Plus petit contributeur (hors zéro): {rows[0].get('member_name')} avec {float(rows[0].get('kg', 0.0)):.1f} kg."
        return "Donnée non disponible pour cette requête précise."
    if payload.get("largest_parcel_by_product") is not None:
        rows = payload.get("largest_parcel_by_product", [])
        if rows:
            row = rows[0]
            return f"Plus grande parcelle: {row.get('parcel_name')} ({float(row.get('surface_ha', 0.0)):.2f} ha), membre {row.get('member_name')}."
        return "Donnée non disponible pour cette requête précise."
    if payload.get("top_grade_by_volume") is not None:
        rows = payload.get("top_grade_by_volume", [])
        if rows:
            return f"Grade dominant: {rows[0].get('grade')} avec {float(rows[0].get('kg', 0.0)):.1f} kg."
        return "Donnée non disponible pour cette requête précise."
    if payload.get("top_collection_days") is not None:
        rows = payload.get("top_collection_days", [])
        if rows:
            return "Top jours collecte: " + "; ".join(f"{r.get('date')} ({float(r.get('kg', 0.0)):.1f} kg)" for r in rows[:3])
        return "Donnée non disponible pour cette requête précise."
    if payload.get("available_stock_gap") is not None:
        rows = payload.get("available_stock_gap", [])
        if rows:
            row = rows[0]
            return f"{row.get('product')}: disponible net {float(row.get('available_kg', 0.0)):.1f} kg, écart au seuil {float(row.get('gap_kg', 0.0)):.1f} kg."
        return "Donnée non disponible pour cette requête précise."
    if payload.get("oldest_open_lot") is not None:
        rows = payload.get("oldest_open_lot", [])
        if rows:
            return f"Lot ouvert le plus ancien: {rows[0].get('lot_code')} créé le {rows[0].get('creation_date')}."
        return "Donnée non disponible pour cette requête précise."
    if payload.get("process_stage_loss_ranking") is not None:
        rows = payload.get("process_stage_loss_ranking", [])
        if rows:
            return f"Étape la plus pénalisante: {rows[0].get('stage')} avec {float(rows[0].get('kg_loss', 0.0)):.1f} kg perdus."
        return "Donnée non disponible pour cette requête précise."

    if payload.get("requested_batch_ref") and not payload.get("batch_summary"):
        return f"Je n’ai pas trouvé de lot avec la référence {_display_batch_ref(payload.get('requested_batch_ref'))}."
    if payload.get("cooperative_overview"):
        row = payload["cooperative_overview"][0]
        return (
            "Résumé coopérative: "
            f"{int(row.get('member_count', 0))} membre(s), {int(row.get('parcel_count', 0))} parcelle(s), "
            f"{int(row.get('batch_count', 0))} lot(s) dont {int(row.get('open_batch_count', 0))} en cours, "
            f"stock disponible total {float(row.get('stock_total_kg', 0.0)):.1f} kg, "
            f"perte moyenne observée {float(row.get('avg_loss_pct', 0.0)):.1f}%."
        )
    if payload.get("parcel_count") is not None:
        return f"La coopérative compte {int(payload.get('parcel_count', 0) or 0)} parcelle(s) enregistrée(s)."
    if payload.get("parcels_list") is not None:
        rows = payload.get("parcels_list", [])
        if rows:
            lines = [f"Parcelles enregistrées ({len(rows)}):"]
            for row in rows[:20]:
                lines.append(
                    f"- {row.get('parcel_name')}: {float(row.get('surface_ha', 0.0)):.2f} ha | culture {row.get('main_culture')} | membre {row.get('member_name')}"
                )
            return "\\n".join(lines)
        return "Aucune parcelle n’est enregistrée pour cette coopérative."
    # Pre-harvest responses
    if payload.get("parcel_status"):
        items = payload["parcel_status"]
        if items:
            completed_total = sum(item.get("completed", 0) for item in items)
            pending_total = sum(item.get("pending", 0) for item in items)
            return (
                f"Les données de pré-récolte indiquent {completed_total} étapes complétées "
                f"et {pending_total} étapes en attente sur {len(items)} parcelles."
            )
        return "Les données de pré-récolte ne sont pas suffisantes pour confirmer ce point."
    
    if payload.get("preharvest_status"):
        items = payload["preharvest_status"]
        if items:
            return f"Les parcelles suivies en pré-récolte sont au nombre de {len(items)} avec les étapes associées."
        return "Aucune donnée pré-récolte disponible pour le moment."
    
    if payload.get("parcels_missing_data"):
        items = payload["parcels_missing_data"]
        if items:
            return f"{len(items)} parcelle(s) avec données manquantes. Vérifiez les détails pour compléter les informations."
        return "Toutes les parcelles ont les données requises."

    if payload.get("top_farmers") is not None and (
        "classe" in str(payload.get("query_text", "")).lower()
        or "livré" in str(payload.get("query_text", "")).lower()
        or "livre" in str(payload.get("query_text", "")).lower()
        or "plus de kg" in str(payload.get("query_text", "")).lower()
        or "premier" in str(payload.get("query_text", "")).lower()
        or "top" in str(payload.get("query_text", "")).lower()
        or ("detected_module" in payload and str(payload.get("detected_module") or "") == "members")
    ):
        rows = payload.get("top_farmers", [])
        if rows:
            lines = [f"Classement des membres par quantité collectée ({len(rows)}):"]
            for row in rows[:10]:
                lines.append(
                    f"- {row.get('member_name')} ({row.get('member_code')}): {float(row.get('total_quantity_kg', 0.0)):.1f} kg"
                )
            return "\n".join(lines)
        return "Aucune donnée de collecte membre n’est disponible pour établir ce classement."

    if payload.get("collections_summary") is not None:
        rows = payload.get("collections_summary", [])
        if rows:
            total = float(payload.get("collections_total_kg", 0.0) or 0.0)
            lines = [f"Collectes enregistrées ({len(rows)} produits), total {total:.1f} kg:"]
            for row in rows[:10]:
                lines.append(f"- {_fr_product_label(row.get('product'))}: {float(row.get('total_quantity_kg', 0.0)):.1f} kg")
            return "\n".join(lines)
        return "Aucune collecte n’est disponible pour la période demandée."

    if payload.get("members_list") is not None:
        members = payload.get("members_list", [])
        if members:
            previews = []
            for member in members[:5]:
                previews.append(f"{member.get('member_name')} ({member.get('member_code')})")
            suffix = "…" if len(members) > 5 else ""
            return f"Les membres trouvés ({len(members)}) sont: " + ", ".join(previews) + suffix
        return "Aucun membre n’est enregistré pour cette coopérative."

    if payload.get("top_members_by_cost") is not None:
        rows = payload.get("top_members_by_cost", [])
        if rows:
            lines = [f"Classement des membres par coût total ({len(rows)}):"]
            for row in rows[:10]:
                lines.append(
                    f"- {row.get('member_name')} ({row.get('member_code')}): {float(row.get('total_cost_fcfa', 0.0)):.0f} FCFA"
                )
            return "\n".join(lines)
        if payload.get("member_value_module_available") is False:
            return "Le module valeur/coût des membres n’est pas disponible dans le modèle de données actuel."
        return "Le module valeur/coût des membres ne contient pas encore de données."

    if payload.get("high_risk_lots") is not None:
        high_risk_lots = payload.get("high_risk_lots", [])
        if high_risk_lots:
            previews = []
            for item in high_risk_lots[:6]:
                previews.append(
                    f"{_display_batch_ref(item.get('batch_ref'))} ({float(item.get('loss_pct', 0.0)):.1f} % de perte, {float(item.get('efficiency_pct', 0.0)):.1f} % d’efficacité)"
                )
            suffix = "…" if len(high_risk_lots) > 6 else ""
            return f"Les lots à risque élevé détectés ({len(high_risk_lots)}) sont: " + "; ".join(previews) + suffix
        return "Aucun lot à risque élevé n’a été détecté selon les mesures SQL de pertes/efficacité."

    if payload.get("stage_loss_comparison"):
        rows = payload.get("stage_loss_comparison", [])
        if len(rows) >= 2:
            left, right = rows[0], rows[1]
            return (
                f"Comparaison des pertes: {left.get('stage_label')} {float(left.get('avg_loss_pct', 0.0)):.1f} % "
                f"vs {right.get('stage_label')} {float(right.get('avg_loss_pct', 0.0)):.1f} %."
            )
        if rows:
            row = rows[0]
            return f"Perte moyenne {row.get('stage_label')}: {float(row.get('avg_loss_pct', 0.0)):.1f} %."

    if payload.get("in_progress_lots") is not None:
        rows = payload.get("in_progress_lots", [])
        if rows:
            lines = [f"Lots en cours ({len(rows)}):"]
            for row in rows[:20]:
                lines.append(
                    f"- {_display_batch_ref(row.get('batch_ref'))}: perte {float(row.get('loss_pct', 0.0)):.1f} % | efficacité {float(row.get('efficiency_pct', 0.0)):.1f} %"
                )
            return "\n".join(lines)
        return "Aucun lot en cours n’a été trouvé."

    if payload.get("low_efficiency_lots") is not None:
        rows = sorted(
            payload.get("low_efficiency_lots", []),
            key=lambda item: float(item.get("efficiency_pct", 100.0) or 100.0),
        )
        if rows:
            lines = [f"Lots à efficacité faible ({len(rows)}):"]
            for row in rows[:20]:
                lines.append(
                    f"- {_display_batch_ref(row.get('batch_ref'))}: efficacité {float(row.get('efficiency_pct', 0.0)):.1f} % | perte {float(row.get('loss_pct', 0.0)):.1f} %"
                )
            return "\n".join(lines)
        return "Aucun lot à efficacité faible n’a été détecté."
    
    if payload.get("top_loss_batches"):
        item = payload["top_loss_batches"][0]
        return (
            f"Le lot avec le plus de pertes est {_display_batch_ref(item.get('batch_ref'))} "
            f"avec {float(item.get('loss_pct', 0.0)):.1f} % de pertes cumulées."
        )
    
    if payload.get("current_stock"):
        items = payload["current_stock"]
        total_available = float(payload.get("current_stock_total_kg", 0.0) or 0.0)
        if len(items) == 1:
            item = items[0]
            return (
                f"Le stock opérationnel observé pour {_fr_product_label(item.get('product'))} est de "
                f"{item.get('available_stock_kg', 0):.1f} {_normalize_unit(item.get('unit'))} disponibles."
            )
        lines = [f"Les stocks actuels ({len(items)} produits) sont, total disponible {total_available:.1f} kg:"]
        for item in items[:8]:
            lines.append(
                f"- {_fr_product_label(item.get('product'))}: {float(item.get('available_stock_kg', 0.0)):.1f} {_normalize_unit(item.get('unit'))} disponibles"
            )
        if len(items) > 8:
            lines.append("- …")
        return "\n".join(lines)

    if payload.get("invoices_summary") is not None:
        rows = payload.get("invoices_summary", [])
        if rows:
            lines = [f"Factures ({len(rows)}):"]
            for row in rows[:20]:
                lines.append(
                    f"- {row.get('invoice_number')}: statut {row.get('status')} | montant {float(row.get('total_amount_fcfa', 0.0)):.0f} FCFA"
                )
            return "\n".join(lines)
        if payload.get("invoices_module_available") is False:
            return "Le module factures n’est pas disponible dans le modèle de données actuel."
        return "Aucune facture n’est disponible dans les données actuelles."

    if payload.get("commercial_orders") is not None:
        rows = payload.get("commercial_orders", [])
        totals = payload.get("commercial_totals", [])
        if rows:
            lines = [f"Commandes commerciales ({len(rows)}):"]
            for row in rows[:20]:
                lines.append(
                    f"- {row.get('order_number')}: statut {row.get('status')} | montant {float(row.get('total_amount_fcfa', 0.0)):.0f} FCFA"
                )
            if totals:
                total = totals[0]
                lines.append(
                    f"Total commercial: {float(total.get('total_amount_fcfa', 0.0)):.0f} FCFA sur {int(total.get('order_count', 0))} commande(s)."
                )
            return "\n".join(lines)
        if totals:
            total = totals[0]
            if int(total.get("order_count", 0) or 0) == 0:
                return "Aucune commande commerciale n’est disponible dans les données actuelles."
        if payload.get("commercial_module_available") is False:
            return "Le module commercialisation n’est pas disponible dans le modèle de données actuel."
        return "Le module commercialisation n’est pas disponible dans les données actuelles."

    if payload.get("finance_expenses") is not None:
        rows = payload.get("finance_expenses", [])
        if rows:
            row = rows[0]
            treasury_count = int(row.get("treasury_count", 0) or 0)
            charge_count = int(row.get("global_charge_count", 0) or 0)
            if treasury_count == 0 and charge_count == 0:
                return "Aucune charge ou dépense n’est disponible dans les données actuelles."
            return (
                "Synthèse charges/dépenses: "
                f"{treasury_count} transaction(s) trésorerie pour {float(row.get('treasury_total_fcfa', 0.0)):.0f} FCFA, "
                f"{charge_count} charge(s) globales pour {float(row.get('global_charge_total_fcfa', 0.0)):.0f} FCFA."
            )
        if payload.get("finance_module_available") is False:
            return "Le module finance n’est pas disponible dans le modèle de données actuel."
        return "Le module finance n’est pas disponible dans les données actuelles."
    if payload.get("material_balance_global"):
        item = payload["material_balance_global"]
        return (
            "Bilan matière global: "
            f"entrée {float(item.get('input_quantity', 0.0)):.1f} kg, "
            f"sortie {float(item.get('output_quantity', 0.0)):.1f} kg, "
            f"perte {float(item.get('loss_percentage', 0.0)):.1f}%."
        )

    if payload.get("material_balance"):
        item = payload["material_balance"][0]
        return (
            f"Le bilan matière du lot {_display_batch_ref(item.get('batch_ref'))} montre une perte de "
            f"{float(item.get('loss_percentage', 0.0)):.1f} % et une efficacité de "
            f"{float(item.get('efficiency_percentage', 0.0)):.1f} %."
        )
    if payload.get("top_process_stage"):
        item = payload.get("top_process_stage") or {}
        return (
            f"L’étape critique observée est {_fr_stage_label(item.get('stage'))} "
            f"avec {float(item.get('loss_pct', 0.0)):.1f} % de pertes."
        )

    if payload.get("process_step_losses"):
        item = max(payload["process_step_losses"], key=lambda row: float(row.get("loss_pct", 0.0) or 0.0))
        return (
            f"L’étape critique observée est {_fr_stage_label(item.get('stage'))} sur {_display_batch_ref(item.get('batch_ref'))} "
            f"avec {float(item.get('loss_pct', 0.0)):.1f} % de pertes."
            )
    if payload.get("stage_efficiency_summary"):
        rows = payload["stage_efficiency_summary"]
        item = max(rows, key=lambda row: float(row.get("avg_loss_pct", 0.0) or 0.0))
        return (
            "Les pertes par étape montrent un signal principal sur "
            f"{_fr_stage_label(item.get('stage'))}: {float(item.get('avg_loss_pct', 0.0)):.1f} % en moyenne."
        )
    if payload.get("batch_summary"):
        item = payload["batch_summary"][0]
        return (
            f"Le lot {_display_batch_ref(item.get('batch_ref'))} présente une perte cumulée de {float(item.get('loss_pct', 0.0)):.1f} % "
            f"et une efficacité de {float(item.get('efficiency_pct', 0.0)):.1f} %."
        )
    return "Aucune mesure opérationnelle exploitable n’a été trouvée pour cette demande."


def _display_batch_ref(value) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "lot inconnu"
    parts = raw.split("-")
    pretty = []
    for part in parts:
        if part.isalpha():
            pretty.append(part.capitalize())
        else:
            pretty.append(part)
    return "-".join(pretty)


def _fr_product_label(value) -> str:
    normalized = str(value or "").strip().lower()
    mapping = {
        "mango": "Mangue",
        "mangue": "Mangue",
        "peanut": "Arachide",
        "arachide": "Arachide",
        "millet": "Mil",
        "mil": "Mil",
    }
    return mapping.get(normalized, str(value or "Produit"))


def _fr_stage_label(value) -> str:
    normalized = str(value or "").strip().lower()
    mapping = {
        "drying": "séchage",
        "sorting": "tri",
        "packaging": "emballage",
        "cleaning": "nettoyage",
    }
    return mapping.get(normalized, str(value or "étape"))


def _normalize_unit(value) -> str:
    normalized = str(value or "kg").strip().lower()
    mapping = {
        "kg": "kg",
        "kilogram": "kg",
        "kilograms": "kg",
        "t": "tonnes",
        "ton": "tonnes",
        "tons": "tonnes",
        "tonne": "tonnes",
        "tonnes": "tonnes",
        "fcfa": "FCFA",
        "xof": "FCFA",
        "%": "%",
    }
    return mapping.get(normalized, str(value or "kg"))


def _apply_post_aggregation_checks(payload: dict[str, Any]) -> dict[str, Any]:
    data = dict(payload or {})

    top_farmers = data.get("top_farmers")
    if isinstance(top_farmers, list) and top_farmers:
        data["top_farmers"] = sorted(
            top_farmers,
            key=lambda row: float((row or {}).get("total_quantity_kg", 0.0) or 0.0),
            reverse=True,
        )

    stocks = data.get("current_stock")
    if isinstance(stocks, list) and stocks:
        data["current_stock_total_kg"] = float(
            sum(float((row or {}).get("available_stock_kg", 0.0) or 0.0) for row in stocks)
        )

    process_rows = data.get("process_step_losses")
    if isinstance(process_rows, list) and process_rows:
        top = max(process_rows, key=lambda row: float((row or {}).get("loss_pct", 0.0) or 0.0))
        data["top_process_stage"] = {
            "stage": str((top or {}).get("stage") or ""),
            "loss_pct": float((top or {}).get("loss_pct", 0.0) or 0.0),
        }

    balance_rows = data.get("material_balance")
    if isinstance(balance_rows, list) and balance_rows:
        in_kg = float(sum(float((row or {}).get("input_quantity", 0.0) or 0.0) for row in balance_rows))
        out_kg = float(sum(float((row or {}).get("output_quantity", 0.0) or 0.0) for row in balance_rows))
        loss_pct = ((in_kg - out_kg) / in_kg * 100.0) if in_kg > 0 else 0.0
        data["material_balance_global"] = {
            "input_quantity": in_kg,
            "output_quantity": out_kg,
            "loss_percentage": loss_pct,
        }

    collections = data.get("collections_summary")
    if isinstance(collections, list) and collections:
        data["collections_total_kg"] = float(
            sum(float((row or {}).get("total_quantity_kg", 0.0) or 0.0) for row in collections)
        )

    return data
