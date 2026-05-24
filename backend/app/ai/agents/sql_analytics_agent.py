from __future__ import annotations

import os
import re
import time
import unicodedata
from datetime import date
from typing import Any

from sqlalchemy.exc import OperationalError

from app.ai.agents.base_agent import BaseAgent
from app.ai.schemas.agent_schemas import AgentContext, AgentResult
from app.ai.tools.sql_tools import SQLTools
from app.db.session import set_sql_operation_context

EVIDENCE_HAS = "HAS_EVIDENCE"
EVIDENCE_NO_DATA = "PROVEN_NO_DATA"
EVIDENCE_PARTIAL = "PARTIAL_EVIDENCE"
EVIDENCE_TOOL_ERROR = "TOOL_ERROR"
EVIDENCE_UNSUPPORTED = "UNSUPPORTED"


class SQLAnalyticsAgent(BaseAgent):
    name = "SQLAnalyticsAgent"
    description = "Retrieves structured cooperative operational data via controlled SQL tools."

    def __init__(self, sql_tools: SQLTools):
        self.sql_tools = sql_tools

    async def run(self, query: str, context: AgentContext) -> AgentResult:
        start = time.perf_counter()
        entities = context.detected_entities or {}
        intent_family = str(entities.get("intent_family") or "").strip().upper()
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
        movement_direction = _extract_movement_direction(normalized)

        requested_limit = _extract_requested_limit(normalized)
        member_subject_hint = any(
            token in normalized
            for token in ("membre", "membres", "member", "members", "farmer", "farmers", "producteur", "producteurs")
        )
        asks_member_ranking = member_subject_hint and any(
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
        postharvest_loss_ranking_intent = _is_postharvest_loss_ranking_intent(normalized)
        postharvest_listing_intent = any(
            token in normalized
            for token in (
                "quels sont les lots",
                "quel les lots",
                "list lots",
                "liste lots",
                "liste les lots",
                "lots disponibles",
                "lots enregistres",
                "lots enregistrés",
                "available lots",
                "lots post-recolte",
                "lots post-récolte",
                "lots post harvest",
                "lots postharvest",
            )
        ) and any(
            token in normalized
            for token in ("lot", "lots", "batch", "batches", "disponible", "disponibles", "available", "enregistre", "enregistrés")
        )
        postharvest_analytics_intent = postharvest_loss_ranking_intent or any(
            token in normalized
            for token in (
                "perte",
                "loss",
                "efficacite",
                "efficacité",
                "efficiency",
                "rendement",
                "bilan matiere",
                "bilan matière",
                "material balance",
                "sechage",
                "séchage",
                "nettoyage",
                "tri",
                "emballage",
                "conditionnement",
            )
        )
        preharvest_lot_intent = any(
            token in normalized
            for token in (
                "pre-recolte",
                "pré-récolte",
                "pre recolte",
                "pre-harvest",
                "quantite estimee",
                "quantité estimée",
                "charge estimee",
                "charge estimée",
                "dates prevues",
                "dates prévues",
                "dates reelles",
                "dates réelles",
                "parcelle",
                "culture",
                "etapes pre-recolte",
                "étapes pré-récolte",
                "lifecycle",
            )
        )
        mixed_pre_post_intent = preharvest_lot_intent and postharvest_analytics_intent
        warnings: list[str] = []
        payload: dict[str, Any] = {}
        if os.environ.get("AI_AUDIT_DEBUG") == "1":
            payload["module_capabilities"] = self.sql_tools.get_module_capabilities()
        payload["detected_module"] = module
        payload["query_text"] = query
        if batch_ref:
            payload["requested_batch_ref"] = batch_ref
        sources: list[dict[str, Any]] = []

        contract_result = self._run_contract_sql_dispatch(
            intent_family=intent_family,
            query=query,
            context=context,
            entities=entities,
            product=product,
            batch_ref=batch_ref,
            payload=payload,
            warnings=warnings,
            sources=sources,
            start=start,
        )
        if contract_result is not None:
            return contract_result

        # Deterministic high-precision operations for defense-critical queries.
        op = _detect_deterministic_operation(normalized)
        if op:
            product_for_query = product or _detect_product_from_text(normalized)
            payload["query_operation"] = op
            op_timing: dict[str, Any] = {"sql_execution_ms": None, "db_error_type": None}
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
            elif op == "get_stock_movements_journal":
                r, op_timing = _timed_sql_tool_call(
                    "get_stock_movements_journal",
                    self.sql_tools.get_stock_movements_journal,
                    product=product_for_query,
                    batch_ref=batch_ref,
                    limit=5 if re.search(r"\b5\b|cinq", normalized) else 30,
                    direction=movement_direction,
                )
                payload["stock_movements_journal"] = r.get("items", [])
            elif op == "get_collections_summary":
                r, op_timing = _timed_sql_tool_call(
                    "get_collections_summary",
                    self.sql_tools.get_collections_summary,
                    product=product_for_query,
                    date_range=effective_date_range,
                )
                payload["collections_summary"] = r.get("items", [])
            elif op == "get_top_farmers":
                r, op_timing = _timed_sql_tool_call(
                    "get_top_farmers",
                    self.sql_tools.get_top_farmers,
                    product=product_for_query,
                    date_range=effective_date_range,
                )
                payload["top_farmers"] = r.get("items", [])
            elif op == "get_parcels_list":
                r, op_timing = _timed_sql_tool_call("get_parcels_list", self.sql_tools.get_parcels_list, product=product_for_query)
                payload["parcels_list"] = r.get("items", [])
            elif op == "get_commercial_invoice_linkage":
                r = self.sql_tools.get_commercial_invoice_linkage()
                payload["commercial_invoice_linkage"] = r.get("items", [])
                payload["commercial_invoice_linkage_summary"] = r.get("summary", [])
            elif op == "get_treasury_traceability":
                r = self.sql_tools.get_treasury_traceability()
                payload["treasury_traceability"] = r.get("items", [])
                payload["treasury_traceability_summary"] = r.get("summary", [])
            else:
                r = {"items": [], "sources": [], "warnings": []}
                op_timing = {"sql_execution_ms": None, "db_error_type": None}
            sources.extend(r.get("sources", []))
            warnings.extend(r.get("warnings", []))
            op_rows = r.get("items", []) if isinstance(r, dict) else []
            payload["sql_dispatch_trace"] = {
                "intent_family": intent_family or "FACTUAL_SQL",
                "route": str(context.route.value if hasattr(context.route, "value") else context.route),
                "sql_operation": op,
                "tool_name": f"SQLTools.{op}",
                "tool_function": f"SQLTools.{op}",
                "module": module,
                "cooperative_id": str(self.sql_tools.cooperative_id),
                "filters": {
                    "product": product_for_query,
                    "batch_ref": batch_ref,
                    "module": module,
                },
                "row_count": len(op_rows) if isinstance(op_rows, list) else 0,
                "evidence_row_count": len(op_rows) if isinstance(op_rows, list) else 0,
                "evidence_type": "SQL",
                "evidence_status": EVIDENCE_HAS if op_rows else EVIDENCE_NO_DATA,
                "warnings": sorted(set(warnings)),
                "sql_execution_ms": op_timing.get("sql_execution_ms"),
                "db_error_type": op_timing.get("db_error_type"),
            }
            answer_part = _build_sql_answer(payload)
            confidence = 0.9 if op_rows else 0.72
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

        phase3_stock_movement_intent = any(
            token in normalized
            for token in (
                "stock movement",
                "mouvement de stock",
                "mouvements de stock",
                "journal de stock",
                "journal stock",
                "journal des mouvements",
                "journal des mouvement",
                "mouvement",
                "mouvements",
                "movement_type",
                "action_type",
                "source du mouvement",
            )
        ) and any(token in normalized for token in ("stock", "mouvement", "movement", "journal"))
        if _contains_stock_keyword(normalized) and not phase3_stock_movement_intent:
            stock = self.sql_tools.get_current_stock(product=product)
            payload["current_stock"] = stock.get("items", [])
            sources.extend(stock.get("sources", []))
            warnings.extend(stock.get("warnings", []))

        if (module == "members" or any(token in normalized for token in ("membre", "membres", "member", "farmer", "producteur", "producteurs"))) and not asks_member_ranking:
            members, members_timing = _timed_sql_tool_call("get_members_list", self.sql_tools.get_members_list, member_name=member_name)
            payload["members_list"] = members.get("items", [])
            payload["sql_operation_timing"] = {"operation": "get_members_list", **members_timing}
            sources.extend(members.get("sources", []))
            warnings.extend(members.get("warnings", []))

        if asks_member_ranking:
            top_farmers = self.sql_tools.get_top_farmers(product=product, date_range=effective_date_range)
            top_items = top_farmers.get("items", [])
            payload["top_farmers"] = top_items[:requested_limit] if requested_limit else top_items
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

        grouped_by_producer = any(token in normalized for token in ("par producteur", "par producteurs", "par membre", "par membres"))
        if grouped_by_producer:
            top_farmers = self.sql_tools.get_top_farmers(product=product, date_range=effective_date_range)
            payload["top_farmers"] = top_farmers.get("items", [])
            sources.extend(top_farmers.get("sources", []))
            warnings.extend(top_farmers.get("warnings", []))
        elif any(token in normalized for token in ("collect", "collecte", "input")):
            collections, collections_timing = _timed_sql_tool_call(
                "get_collections_summary",
                self.sql_tools.get_collections_summary,
                product=product,
                date_range=effective_date_range,
            )
            payload["collections_summary"] = collections.get("items", [])
            payload["sql_operation_timing"] = {"operation": "get_collections_summary", **collections_timing}
            sources.extend(collections.get("sources", []))
            warnings.extend(collections.get("warnings", []))

        if module == "invoices" or any(token in normalized for token in ("facture", "factures", "invoice", "invoices")):
            payload["invoices_module_available"] = self.sql_tools.module_available("commercial_invoices")
            invoices = self.sql_tools.get_invoices_summary()
            payload["invoices_summary"] = invoices.get("items", [])
            payload["invoices_status_summary"] = invoices.get("status_summary", [])
            sources.extend(invoices.get("sources", []))
            warnings.extend(invoices.get("warnings", []))

        if module == "commercial" or any(
            token in normalized for token in ("commande", "commandes", "vente", "ventes", "commercialisation", "commercial")
        ):
            payload["commercial_module_available"] = self.sql_tools.module_available("commercial_orders")
            orders = self.sql_tools.get_commercial_orders_summary()
            totals = self.sql_tools.get_commercial_totals()
            payload["commercial_orders"] = orders.get("items", [])
            payload["commercial_orders_status_summary"] = orders.get("status_summary", [])
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

        has_bl_token = _has_word(normalized, "bl") or ("input_reference_bl" in normalized)
        phase3_collecte_traceability_intent = (
            (any(token in normalized for token in ("collecte", "collectes", "input")) or has_bl_token)
            and (
                any(token in normalized for token in ("traceabil", "justificatif", "linked lot", "lot lie", "lot lié", "stock impact policy", "validation duplique"))
                or has_bl_token
            )
        )
        if any(token in normalized for token in ("collecte", "collectes", "input")) and any(
            token in normalized for token in ("bl", "justificatif", "lot", "producteur", "produit", "fichier", "statut")
        ):
            phase3_collecte_traceability_intent = True
        if "collecte" in normalized and any(token in normalized for token in ("creation", "création", "validation")) and "stock" in normalized:
            phase3_collecte_traceability_intent = True
        if any(token in normalized for token in ("stock impact policy", "validation duplique", "duplication a la validation", "duplication validation")):
            phase3_collecte_traceability_intent = True
        phase3_file_evidence_intent = any(
            token in normalized
            for token in (
                "uploaded file",
                "fichier upload",
                "fichiers upload",
                "fichier",
                "fichiers",
                "upload",
                "devis",
                "justificatif",
                "file_url",
                "evidence document",
                "preuve documentaire",
            )
        )
        phase3_advance_intent = any(
            token in normalized
            for token in (
                "avance",
                "avances",
                "farmer advance",
                "treasury sync",
                "devis status",
                "avance producteur",
                "avances producteur",
            )
        )
        phase3_treasury_intent = any(
            token in normalized
            for token in (
                "status tresorerie",
                "status treasury",
                "statut tresorerie",
                "statut treasury",
                "receipt_reference",
                "enregistre_complet",
                "transaction sans justificatif",
                "transactions sans justificatif",
                "transactions missing justificatif",
                "transaction complete",
                "transaction verrouillee",
                "transaction verrouille",
                "tresorerie",
                "trésorerie",
            )
        )
        phase3_commercial_link_intent = any(
            token in normalized
            for token in (
                "paid order",
                "commande payee",
                "invoice paid",
                "facture payee",
                "treasury income linked",
                "commercial invoice generated income",
                "idempotency",
                "lien facture",
                "lien tresorerie",
                "paid orders",
                "generated invoices",
                "facture generee",
                "factures en statut",
                "revenu tresorerie",
                "chainage",
                "chainage commercial",
            )
        )
        if all(token in normalized for token in ("commande", "facture", "tresorerie")):
            phase3_commercial_link_intent = True
        if phase3_commercial_link_intent:
            phase3_treasury_intent = False
        if phase3_treasury_intent and (
            "transaction" in normalized
            or not any(token in normalized for token in ("avance", "avances", "farmer advance", "producteur"))
        ):
            phase3_advance_intent = False
        if phase3_collecte_traceability_intent and not any(token in normalized for token in ("avance", "avances", "farmer advance")):
            phase3_advance_intent = False

        if phase3_stock_movement_intent:
            movement_rows = self.sql_tools.get_stock_movements_journal(
                product=product,
                batch_ref=batch_ref,
                direction=movement_direction,
            )
            payload["stock_movements_journal"] = movement_rows.get("items", [])
            sources.extend(movement_rows.get("sources", []))
            warnings.extend(movement_rows.get("warnings", []))
        explicit_file_evidence_prompt = any(token in normalized for token in ("uploaded", "upload", "fichier", "file", "evidence"))
        if explicit_file_evidence_prompt and not any(token in normalized for token in ("collecte", "input", "bl", "justificatif")):
            phase3_collecte_traceability_intent = False
        if phase3_advance_intent and not explicit_file_evidence_prompt:
            phase3_file_evidence_intent = False
        if phase3_treasury_intent:
            phase3_collecte_traceability_intent = False
        if phase3_file_evidence_intent and not explicit_file_evidence_prompt:
            # Keep uploaded-files route focused on explicit evidence/file prompts.
            phase3_file_evidence_intent = False

        explicit_traceability_request = any(token in normalized for token in ("collecte", "justificatif", "input_reference_bl", "producteur", "facture", "tresorerie", "trésorerie"))
        if postharvest_loss_ranking_intent and not explicit_traceability_request:
            phase3_collecte_traceability_intent = False
            phase3_file_evidence_intent = False
            phase3_advance_intent = False
            phase3_treasury_intent = False
            phase3_commercial_link_intent = False

        if phase3_collecte_traceability_intent:
            collecte = self.sql_tools.get_collecte_traceability()
            payload["collecte_traceability"] = collecte.get("items", [])
            payload["collecte_traceability_summary"] = collecte.get("summary", [])
            sources.extend(collecte.get("sources", []))
            warnings.extend(collecte.get("warnings", []))
        if phase3_file_evidence_intent:
            file_ev = self.sql_tools.get_uploaded_files_evidence()
            payload["uploaded_files_evidence"] = file_ev.get("items", [])
            payload["uploaded_files_evidence_summary"] = file_ev.get("summary", [])
            sources.extend(file_ev.get("sources", []))
            warnings.extend(file_ev.get("warnings", []))
        if phase3_advance_intent:
            adv = self.sql_tools.get_farmer_advances_traceability()
            payload["farmer_advances_traceability"] = adv.get("items", [])
            payload["farmer_advances_traceability_summary"] = adv.get("summary", [])
            sources.extend(adv.get("sources", []))
            warnings.extend(adv.get("warnings", []))
        if phase3_treasury_intent:
            tx = self.sql_tools.get_treasury_traceability()
            payload["treasury_traceability"] = tx.get("items", [])
            payload["treasury_traceability_summary"] = tx.get("summary", [])
            sources.extend(tx.get("sources", []))
            warnings.extend(tx.get("warnings", []))
        if phase3_commercial_link_intent:
            links = self.sql_tools.get_commercial_invoice_linkage()
            payload["commercial_invoice_linkage"] = links.get("items", [])
            payload["commercial_invoice_linkage_summary"] = links.get("summary", [])
            sources.extend(links.get("sources", []))
            warnings.extend(links.get("warnings", []))

        # Handle post-harvest lot listing intent (separate from ranking/loss queries)
        if postharvest_listing_intent and not batch_ref and not postharvest_loss_ranking_intent:
            available_lots = self.sql_tools.get_available_postharvest_lots(product=product)
            payload["available_postharvest_lots"] = available_lots.get("items", [])
            sources.extend(available_lots.get("sources", []))
            warnings.extend(available_lots.get("warnings", []))

        allow_batch_summary = (
            module in {"post_harvest", "material_balance", "lots", "cooperative_summary", "global"}
            or intent_family in {"LOSS_RANKING", "INPUT_OUTPUT_GAP", "LOT_COMPARISON", "STAGE_LOSS_ANALYSIS", "RISK_ANALYSIS"}
            or postharvest_analytics_intent
        )
        if (batch_ref or any(token in normalized for token in ("lot", "batch"))) and allow_batch_summary and not reset_lot_context and (not preharvest_lot_intent or mixed_pre_post_intent):
            batch = (
                self.sql_tools.get_postharvest_batch_summary(batch_ref=batch_ref, product=product)
                if postharvest_analytics_intent
                else self.sql_tools.get_batch_summary(batch_ref=batch_ref)
            )
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
            asks_top_loss = any(
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
            )
            if asks_top_loss:
                high_risk_lots = self.sql_tools.get_high_risk_lots()
                if postharvest_analytics_intent:
                    payload["high_risk_lots"] = [
                        row for row in (payload.get("batch_summary") or []) if bool(row.get("is_consistent")) and row.get("loss_pct") is not None
                    ]
                    payload["high_risk_lots"] = sorted(
                        payload["high_risk_lots"],
                        key=lambda item: float(item.get("loss_pct", 0.0) or 0.0),
                        reverse=True,
                    )[:10]
                else:
                    payload["high_risk_lots"] = high_risk_lots.get("items", [])
                sources.extend(high_risk_lots.get("sources", []))
                warnings.extend(high_risk_lots.get("warnings", []))
                # Anchor "worst-loss lot" on process-step losses when available.
                loss_rows = (
                    self.sql_tools.get_postharvest_process_step_losses(batch_ref=None, stage=None, product=product, date_range=effective_date_range).get("items", [])
                    if postharvest_analytics_intent
                    else self.sql_tools.get_process_step_losses(batch_ref=None, stage=None, product=product, date_range=effective_date_range).get("items", [])
                )
                by_batch: dict[str, dict[str, Any]] = {}
                for row in loss_rows:
                    key = str(row.get("batch_ref") or "").strip()
                    if not key:
                        continue
                    current = by_batch.get(key)
                    loss_pct = float(row.get("loss_pct", 0.0) or 0.0)
                    if current is None or loss_pct > float(current.get("loss_pct", 0.0) or 0.0):
                        by_batch[key] = {"batch_ref": key, "loss_pct": loss_pct}
                if by_batch:
                    payload["top_loss_batches"] = sorted(
                        by_batch.values(),
                        key=lambda item: float(item.get("loss_pct", 0.0) or 0.0),
                        reverse=True,
                    )[:5]
                else:
                    payload["top_loss_batches"] = sorted(
                        batch.get("items", []),
                        key=lambda item: float(item.get("loss_pct", 0.0) or 0.0),
                        reverse=True,
                    )[:5]

        if any(token in normalized for token in ("perte", "loss", "efficacit", "efficiency", "sechage", "tri", "drying", "sorting", "emballage", "packaging")) and (not preharvest_lot_intent or mixed_pre_post_intent):
            losses = (
                self.sql_tools.get_postharvest_process_step_losses(
                    batch_ref=batch_ref,
                    stage=stage,
                    product=product,
                    date_range=effective_date_range,
                )
                if postharvest_analytics_intent
                else self.sql_tools.get_process_step_losses(
                    batch_ref=batch_ref,
                    stage=stage,
                    product=product,
                    date_range=effective_date_range,
                )
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
                    batch_all = (
                        self.sql_tools.get_postharvest_batch_summary(batch_ref=None, product=product)
                        if postharvest_analytics_intent
                        else self.sql_tools.get_batch_summary(batch_ref=None)
                    )
                    payload["low_efficiency_lots"] = [
                        row
                        for row in (batch_all.get("items", []) or [])
                        if row.get("efficiency_pct") is not None and float(row.get("efficiency_pct", 0.0) or 0.0) < 85.0
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

        if ("bilan" in normalized or "material balance" in normalized or "matiere" in normalized) and (not preharvest_lot_intent or mixed_pre_post_intent):
            balance = (
                self.sql_tools.get_postharvest_material_balance(batch_ref=batch_ref, product=product)
                if postharvest_analytics_intent
                else self.sql_tools.get_material_balance(batch_ref=batch_ref, product=product)
            )
            payload["material_balance"] = balance.get("items", [])
            sources.extend(balance.get("sources", []))
            warnings.extend(balance.get("warnings", []))

        contains_member_top_intent = bool(
            re.search(r"\b(membre|producteur|farmer)s?\b", normalized)
            and (
                re.search(r"\b(top|classement|classer|plus\s+gros)\b", normalized)
                or re.search(r"\bmeilleur(?:e|es)?\b", normalized)
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

        if preharvest_lot_intent and not mixed_pre_post_intent:
            payload["lot_domain"] = "PRE_HARVEST_LOT"
            payload.pop("batch_summary", None)
            payload.pop("process_step_losses", None)
            payload.pop("material_balance", None)
            payload.pop("stage_efficiency_summary", None)
            payload.pop("high_risk_lots", None)
            payload.pop("top_loss_batches", None)
            payload.pop("low_efficiency_lots", None)
        elif postharvest_analytics_intent:
            payload["lot_domain"] = "POST_HARVEST_BATCH"

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
        _ensure_sql_dispatch_trace(
            payload=payload,
            intent_family=intent_family or "FACTUAL_SQL",
            route=context.route,
            module=module,
            product=product,
            batch_ref=batch_ref,
            cooperative_id=self.sql_tools.cooperative_id,
            warnings=warnings,
        )

        if context.route.value == "SQL_ONLY" and _is_operational_sql_query(normalized):
            trace = payload.get("sql_dispatch_trace") or {}
            if not trace.get("sql_operation"):
                unsupported_module = _normalize_module_for_unsupported(module, normalized=normalized)
                trace["sql_operation"] = f"UNSUPPORTED_{unsupported_module}_CAPABILITY"
                trace["tool_name"] = "SQLTools.unsupported"
                trace["tool_function"] = "SQLTools.unsupported"
                trace["module"] = module
                trace["row_count"] = 0
                trace["evidence_row_count"] = 0
                trace["evidence_status"] = EVIDENCE_UNSUPPORTED
                trace["warnings"] = sorted(set([*warnings, "SQL_CAPABILITY_UNSUPPORTED"]))
                payload["sql_dispatch_trace"] = trace
                warnings.append("SQL_CAPABILITY_UNSUPPORTED")
            answer_part = "Cette capacité SQL n’est pas encore prise en charge pour ce module. Reformulez avec une opération disponible (stock, lots, bilan matière, commandes, factures, trésorerie)."
            confidence = 0.25
        else:
            answer_part = _build_sql_answer(payload)
            trace = payload.get("sql_dispatch_trace") or {}
            trace_status = _derive_sql_evidence_status(trace=trace, warnings=warnings)
            trace["evidence_status"] = trace_status
            payload["sql_dispatch_trace"] = trace
            evidence_rows = int(trace.get("evidence_row_count") or trace.get("row_count") or 0)
            if trace_status == EVIDENCE_UNSUPPORTED:
                confidence = 0.25
            elif trace_status == EVIDENCE_TOOL_ERROR:
                confidence = 0.2
            elif trace_status == EVIDENCE_NO_DATA:
                confidence = 0.72
            elif trace_status == EVIDENCE_PARTIAL:
                confidence = 0.48
            else:
                confidence = 0.88 if evidence_rows > 0 else 0.48

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

    def _run_contract_sql_dispatch(
        self,
        *,
        intent_family: str,
        query: str,
        context: AgentContext,
        entities: dict[str, Any],
        product: str | None,
        batch_ref: str | None,
        payload: dict[str, Any],
        warnings: list[str],
        sources: list[dict[str, Any]],
        start: float,
    ) -> AgentResult | None:
        if bool(entities.get("needs_batch_clarification")):
            return AgentResult(
                agent_name=self.name,
                route=context.route,
                answer_part="De quel lot parlez-vous ? Indiquez une référence comme LOT-MILX-001.",
                data={"sql_dispatch_trace": {"intent_family": "FOLLOW_UP", "sql_operation": "clarification_required", "row_count": 0}},
                sources=[],
                confidence=0.35,
                warnings=[],
                execution_time_ms=int((time.perf_counter() - start) * 1000),
            )
        if bool(entities.get("needs_recency_clarification")):
            return AgentResult(
                agent_name=self.name,
                route=context.route,
                answer_part=(
                    "Je ne peux pas déterminer de façon fiable le producteur le plus récemment livré avec les opérations SQL disponibles. "
                    "Je peux soit classer les producteurs par quantité livrée, soit vous donner les dernières livraisons brutes."
                ),
                data={"sql_dispatch_trace": {"intent_family": "FOLLOW_UP", "sql_operation": "clarification_required", "row_count": 0}},
                sources=[],
                confidence=0.45,
                warnings=[],
                execution_time_ms=int((time.perf_counter() - start) * 1000),
            )
        normalized = _normalize_text(query)
        if ("efficacite" in normalized) and any(token in normalized for token in ("producteur", "producteurs", "membre", "membres")):
            return AgentResult(
                agent_name=self.name,
                route=context.route,
                answer_part="Cette efficacité producteur n’est pas calculable de manière fiable avec les données disponibles. Données manquantes: sorties/pertes attribuées par producteur sur la même période.",
                data={"sql_dispatch_trace": {"intent_family": intent_family, "sql_operation": "producer_efficiency_unsupported", "row_count": 0, "evidence_status": EVIDENCE_UNSUPPORTED}},
                sources=[],
                confidence=0.55,
                warnings=[],
                execution_time_ms=int((time.perf_counter() - start) * 1000),
            )

        if intent_family not in {
            "STOCK_CURRENT",
            "POSTHARVEST_AVAILABLE_LOTS",
            "LOSS_RANKING",
            "INPUT_OUTPUT_GAP",
            "LOT_COMPARISON",
            "STAGE_LOSS_ANALYSIS",
            "PREHARVEST_STEPS",
            "EXPLANATION_CAUSAL",
            "RISK_ANALYSIS",
            "RECOMMENDATION",
            "LOT_SPECIFIC_RECOMMENDATION",
            "FOLLOW_UP",
        }:
            return None

        sql_operation = ""
        tool_function = ""
        op_timing: dict[str, Any] = {"sql_execution_ms": None, "db_error_type": None}

        if intent_family == "STOCK_CURRENT":
            sql_operation = "get_current_stock"
            tool_function = "SQLTools.get_current_stock"
            result, op_timing = _timed_sql_tool_call(sql_operation, self.sql_tools.get_current_stock, product=product)
            payload["current_stock"] = result.get("items", [])
        elif intent_family == "POSTHARVEST_AVAILABLE_LOTS":
            sql_operation = "get_available_postharvest_lots"
            tool_function = "SQLTools.get_available_postharvest_lots"
            result, op_timing = _timed_sql_tool_call(sql_operation, self.sql_tools.get_available_postharvest_lots, product=product)
            payload["available_postharvest_lots"] = result.get("items", [])
        elif intent_family in {"LOSS_RANKING", "INPUT_OUTPUT_GAP"}:
            sql_operation = "get_canonical_material_balance"
            tool_function = "SQLTools.get_canonical_material_balance"
            result, op_timing = _timed_sql_tool_call(
                sql_operation, self.sql_tools.get_canonical_material_balance, batch_ref=batch_ref, product=product
            )
            rows = result.get("items", []) or []
            rows = [row for row in rows if row.get("validity_status") == "VALID"]
            sort_key = "loss_pct" if intent_family == "LOSS_RANKING" else "gap_qty"
            payload["material_balance"] = sorted(
                rows,
                key=lambda item: float(item.get(sort_key, 0.0) or 0.0),
                reverse=True,
            )
        elif intent_family == "LOT_COMPARISON":
            sql_operation = "get_canonical_material_balance_for_lots"
            tool_function = "SQLTools.get_canonical_material_balance_for_lots"
            lot_refs = _extract_lot_refs(query, explicit=batch_ref)
            result, op_timing = _timed_sql_tool_call(sql_operation, self.sql_tools.get_canonical_material_balance_for_lots, lot_refs)
            payload["material_balance"] = result.get("items", [])
            payload["comparison_lot_refs"] = lot_refs
        elif intent_family == "STAGE_LOSS_ANALYSIS":
            sql_operation = "get_stage_loss_analysis"
            tool_function = "SQLTools.get_stage_loss_analysis"
            stage = _pick_first(entities.get("stage"))
            result, op_timing = _timed_sql_tool_call(
                sql_operation, self.sql_tools.get_stage_loss_analysis, batch_ref=batch_ref, product=product, stage=stage
            )
            payload["stage_loss_analysis"] = result.get("items", [])
        elif intent_family == "PREHARVEST_STEPS":
            sql_operation = "get_parcel_preharvest_status"
            tool_function = "SQLTools.preharvest.get_parcel_preharvest_status"
            result, op_timing = _timed_sql_tool_call(sql_operation, self.sql_tools.preharvest.get_parcel_preharvest_status, product=product)
            payload["preharvest_status"] = result.get("data", [])
        elif intent_family == "EXPLANATION_CAUSAL":
            stage = _pick_first(entities.get("stage"))
            normalized_q = query.lower()
            if stage or any(token in normalized_q for token in ("sechage", "séchage", "tri", "emballage", "conditionnement", "etape", "étape")):
                sql_operation = "get_stage_loss_analysis"
                tool_function = "SQLTools.get_stage_loss_analysis"
                result, op_timing = _timed_sql_tool_call(
                    sql_operation, self.sql_tools.get_stage_loss_analysis, batch_ref=batch_ref, product=product, stage=stage
                )
                payload["stage_loss_analysis"] = result.get("items", [])
            else:
                sql_operation = "get_canonical_material_balance"
                tool_function = "SQLTools.get_canonical_material_balance"
                result, op_timing = _timed_sql_tool_call(
                    sql_operation, self.sql_tools.get_canonical_material_balance, batch_ref=batch_ref, product=product
                )
                payload["material_balance"] = result.get("items", [])
        elif intent_family == "RISK_ANALYSIS":
            sql_operation = "get_canonical_material_balance"
            tool_function = "SQLTools.get_canonical_material_balance"
            result, op_timing = _timed_sql_tool_call(
                sql_operation, self.sql_tools.get_canonical_material_balance, batch_ref=batch_ref, product=product
            )
            rows = result.get("items", []) or []
            payload["high_risk_lots"] = sorted(
                [row for row in rows if row.get("validity_status") == "VALID"],
                key=lambda item: float(item.get("loss_pct", 0.0) or 0.0),
                reverse=True,
            )[:10]
        else:  # RECOMMENDATION / LOT_SPECIFIC_RECOMMENDATION / FOLLOW_UP
            sql_operation = "get_canonical_material_balance"
            tool_function = "SQLTools.get_canonical_material_balance"
            result, op_timing = _timed_sql_tool_call(
                sql_operation, self.sql_tools.get_canonical_material_balance, batch_ref=batch_ref, product=product
            )
            payload["material_balance"] = result.get("items", [])

        sources.extend(result.get("sources", []))
        warnings.extend(result.get("warnings", []))
        payload = _apply_post_aggregation_checks(payload)

        primary_rows = self._primary_rows_for_intent(payload, intent_family)
        trace = {
            "intent_family": intent_family,
            "route": str(context.route.value if hasattr(context.route, "value") else context.route),
            "sql_operation": sql_operation,
            "tool_name": tool_function,
            "tool_function": tool_function,
            "module": entities.get("module"),
            "cooperative_id": str(self.sql_tools.cooperative_id),
            "filters": {
                "product": product,
                "batch_ref": batch_ref,
                "module": entities.get("module"),
            },
            "row_count": len(primary_rows),
            "evidence_row_count": len(primary_rows),
            "evidence_type": "SQL",
            "evidence_status": EVIDENCE_HAS if primary_rows else EVIDENCE_NO_DATA,
            "warnings": sorted(set(warnings)),
            "sql_execution_ms": op_timing.get("sql_execution_ms"),
            "db_error_type": op_timing.get("db_error_type"),
        }
        payload["sql_dispatch_trace"] = trace

        if not primary_rows and "NO_SQL_DATA" not in warnings:
            warnings.append("NO_SQL_DATA")

        answer_part = _build_sql_answer(payload)
        if primary_rows and "SQL_DATA_INCOMPLETE" not in warnings:
            confidence = 0.88
        elif primary_rows:
            confidence = 0.48
        else:
            confidence = 0.72
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

    def _primary_rows_for_intent(self, payload: dict[str, Any], intent_family: str) -> list[dict[str, Any]]:
        if intent_family == "STOCK_CURRENT":
            return list(payload.get("current_stock") or [])
        if intent_family == "POSTHARVEST_AVAILABLE_LOTS":
            return list(payload.get("available_postharvest_lots") or [])
        if intent_family == "STAGE_LOSS_ANALYSIS":
            return list(payload.get("stage_loss_analysis") or [])
        if intent_family in {"LOSS_RANKING", "INPUT_OUTPUT_GAP", "EXPLANATION_CAUSAL", "RECOMMENDATION", "FOLLOW_UP"}:
            return list(payload.get("material_balance") or [])
        if intent_family in {"LOT_COMPARISON", "LOT_SPECIFIC_RECOMMENDATION"}:
            return list(payload.get("material_balance") or [])
        if intent_family == "PREHARVEST_STEPS":
            return list(payload.get("preharvest_status") or [])
        if intent_family == "RISK_ANALYSIS":
            return list(payload.get("high_risk_lots") or [])
        return []


def _pick_first(value):
    if isinstance(value, list) and value:
        return value[0]
    if isinstance(value, str):
        return value
    return None


def _timed_sql_tool_call(operation: str, fn, *args, **kwargs) -> tuple[dict[str, Any], dict[str, Any]]:
    started_at = time.perf_counter()
    set_sql_operation_context(operation)
    try:
        result = fn(*args, **kwargs)
        return result, {"sql_execution_ms": int((time.perf_counter() - started_at) * 1000), "db_error_type": None}
    except OperationalError:
        raise
    except Exception:
        raise
    finally:
        set_sql_operation_context(None)


def _extract_days(text: str, default_days: int) -> int:
    m = re.search(r"(\d+)\s*jour", text)
    if m:
        return max(1, int(m.group(1)))
    m = re.search(r"(\d+)\s*mois", text)
    if m:
        return max(1, int(m.group(1)) * 30)
    return default_days


def _extract_requested_limit(text: str) -> int | None:
    normalized = _normalize_text(text)
    m = re.search(r"\btop\s*(\d+)\b", normalized)
    if m:
        return max(1, int(m.group(1)))
    if "une seule" in normalized or "uniquement" in normalized or "seulement" in normalized:
        return 1
    if "top 1" in normalized or "premier" in normalized:
        return 1
    return None


def _extract_movement_direction(normalized: str) -> str | None:
    text = _normalize_text(normalized)
    if any(token in text for token in ("sortant", "sortants", "sortie", "sorties", "outbound", "out")):
        return "out"
    if any(token in text for token in ("entrant", "entrants", "entree", "entrees", "entrée", "entrées", "inbound", "in")):
        return "in"
    return None


def _detect_deterministic_operation(normalized: str) -> str | None:
    if "stock" in normalized and any(token in normalized for token in ("mouvement", "mouvements", "journal", "historique", "nature", "origine")):
        return "get_stock_movements_journal"
    if "stock" in normalized and any(token in normalized for token in ("sortie", "sorties", "sortant", "sortants", "entree", "entrees", "entrée", "entrées", "entrant", "entrants")):
        return "get_stock_movements_journal"
    if ("stock" in normalized or "produit" in normalized) and any(token in normalized for token in ("seuil", "rupture", "sous le seuil", "proche du seuil")):
        return "get_low_stock_alerts"
    if ("stock" in normalized or "produit" in normalized) and all(token in normalized for token in ("total", "disponible")):
        return "get_current_stock"
    if any(token in normalized for token in ("disponible", "reserve", "restant")) and any(token in normalized for token in ("mangue", "arachide", "mil", "bissap", "produit")):
        return "get_current_stock"
    if any(token in normalized for token in ("combien", "reste", "restant", "restante", "disponible", "disponibles")) and any(
        token in normalized for token in ("mangue", "arachide", "mil", "bissap", "produit", "kg", "kilogramme", "kilogrammes")
    ):
        return "get_current_stock"
    if any(token in normalized for token in ("collecte", "collectes", "collecte", "collectees", "collectées")) and any(
        token in normalized for token in ("par producteur", "par producteurs", "par membre", "par membres")
    ):
        return "get_top_farmers"
    if any(token in normalized for token in ("collecte", "collectes", "collecte", "collectees", "collectées")) and not any(
        token in normalized for token in ("bl", "justificatif", "traceabil", "preuve", "lot lie", "lot lié")
    ) and any(token in normalized for token in ("par produit", "quantite", "quantité", "cumulee", "cumulée", "agreg", "agrèg", "domine")):
        return "get_collections_summary"
    if any(token in normalized for token in ("producteur", "producteurs", "membre", "membres")) and any(
        token in normalized for token in ("livre", "livré", "livrer", "volume", "quantite", "quantité")
    ) and any(token in normalized for token in ("plus", "top", "classement", "grand")):
        return "get_top_farmers"
    if any(token in normalized for token in ("producteurs actifs", "producteur actifs", "membres actifs")) and any(
        token in normalized for token in ("parcelle", "parcelles", "produit", "produits")
    ):
        return "get_parcels_list"
    if any(token in normalized for token in ("commande", "commandes")) and any(token in normalized for token in ("payee", "payées", "payees", "payé", "paye")) and any(
        token in normalized for token in ("sans facture", "facture rattachee", "facture rattachée", "facture liee", "facture liée")
    ):
        return "get_commercial_invoice_linkage"
    if any(token in normalized for token in ("tresorerie", "trésorerie", "transaction", "transactions")) and any(
        token in normalized for token in ("justificatif", "recu", "reçu", "receipt_reference", "reference", "référence", "preuve")
    ):
        return "get_treasury_traceability"
    if (
        "trimestre" in normalized
        and re.search(r"\bmoyenn?e?s?\b", normalized)
        and re.search(r"\bfactur\w*\b", normalized)
        and re.search(r"\b(pay\w*|regl\w*)\b", normalized)
    ):
        return "avg_paid_invoices_current_quarter"
    if "client" in normalized and (
        "plus gros cumul" in normalized
        or "plus de commandes" in normalized
        or "cumul de commandes" in normalized
        or "top client" in normalized
    ):
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


def _is_postharvest_loss_ranking_intent(normalized: str) -> bool:
    txt = str(normalized or "")
    entity_terms = bool(re.search(r"\b(lot|lots|batch|batches)\b", txt))
    rank_terms = bool(re.search(r"\b(top|classement|classe|ranking|critiques?|prioris|pire|pires|plus elev|plus eleve|plus fortes?|plus hauts?|plus\s+penalis\w*)\b", txt))
    metric_terms = bool(
        re.search(r"\b(perte|pertes|loss|efficacite|efficacité|efficiency|rendement|matiere|matière|material balance|bilan matiere|bilan matière)\b", txt)
        or re.search(r"\b(ecarts?|écarts?|gap|difference)\b.*\b(entree|entrée|input)\b.*\b(sortie|output)\b", txt)
    )
    patterns = (
        r"\b(top|classement|ranking)\b.*\b(lot|lots|batch|batches)\b.*\b(perte|loss|efficacite|efficacité|efficiency)\b",
        r"\b(pertes?\s+les?\s+plus|highest\s+loss|worst\s+loss)\b",
        r"\b(lots?\s+critiques?|critical\s+post-?harvest\s+batches)\b",
        r"\b(pire\s+efficacite|pire\s+efficacité|lowest\s+efficiency)\b",
        r"\b(ecarts?|écarts?|gap|difference)\b.*\b(entree|entrée|input)\b.*\b(sortie|output)\b",
        r"\b(bilan\s+matiere|bilan\s+matière|material\s+balance)\b.*\b(lot|batch)\b",
        r"\b(loss|efficiency)\s+ranking\b",
        r"\b(rendement\s+le\s+plus\s+faible|plus\s+mauvais\s+rendement|lowest\s+yield)\b",
        r"\b(performance\s+post-?recolte|performance\s+post-?harvest)\b.*\b(lot|batch)\b",
    )
    return (
        any(re.search(p, txt) for p in patterns)
        or (entity_terms and rank_terms and re.search(r"\bpost-?recolte|post-?harvest\b", txt))
        or (entity_terms and metric_terms and (rank_terms or "par lot" in txt or "par batch" in txt))
    )


def _normalize_text(value: str) -> str:
    raw = str(value or "").lower()
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return " ".join(raw.split())


def _normalize_module_for_unsupported(module: str, *, normalized: str) -> str:
    value = str(module or "").strip().upper()
    if value and value != "GLOBAL":
        return re.sub(r"[^A-Z0-9]+", "_", value).strip("_")
    if any(token in normalized for token in ("facture", "invoice")):
        return "INVOICES"
    if any(token in normalized for token in ("commande", "vente", "commercial")):
        return "COMMERCIAL"
    if any(token in normalized for token in ("tresorerie", "trésorerie", "finance", "charge")):
        return "FINANCE"
    if any(token in normalized for token in ("collecte", "input", "bl", "justificatif")):
        return "INPUTS"
    if any(token in normalized for token in ("membre", "farmer", "producteur")):
        return "MEMBERS"
    if any(token in normalized for token in ("lot", "batch", "bilan", "matiere", "étape", "etape")):
        return "POST_HARVEST"
    if "stock" in normalized:
        return "STOCKS"
    return "SQL"


def _first_list_payload(payload: dict[str, Any], keys: list[str]) -> tuple[str | None, list[dict[str, Any]]]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return key, value
    return None, []


def _infer_sql_operation_from_payload(payload: dict[str, Any], *, module: str) -> tuple[str | None, str | None, int]:
    query_operation = str(payload.get("query_operation") or "").strip()
    if query_operation:
        rows = payload.get(query_operation)
        if isinstance(rows, list):
            return query_operation, f"SQLTools.{query_operation}", len(rows)
        return query_operation, f"SQLTools.{query_operation}", 0

    op_key_map = {
        "collecte_traceability": "get_collecte_traceability",
        "uploaded_files_evidence": "get_uploaded_files_evidence",
        "treasury_traceability": "get_treasury_traceability",
        "commercial_invoice_linkage": "get_commercial_invoice_linkage",
        "commercial_orders": "get_commercial_orders_summary",
        "commercial_totals": "get_commercial_totals",
        "invoices_summary": "get_invoices_summary",
        "finance_expenses": "get_finance_expenses",
        "top_customer_by_orders": "top_customer_by_orders",
        "current_stock": "get_current_stock",
        "low_stock_alerts": "get_low_stock_alerts",
        "stock_movements_journal": "get_stock_movements_journal",
        "available_postharvest_lots": "get_available_postharvest_lots",
        "material_balance": "get_canonical_material_balance",
        "stage_loss_analysis": "get_stage_loss_analysis",
        "process_step_losses": "get_process_step_losses",
        "stage_efficiency_summary": "get_stage_efficiency_summary",
        "collections_summary": "get_collections_summary",
        "members_list": "get_members_list",
        "top_farmers": "get_top_farmers",
        "top_members_by_cost": "get_top_members_by_cost",
        "cooperative_overview": "get_cooperative_overview",
        "farmer_advances_traceability": "get_farmer_advances_traceability",
        "top_grade_by_volume": "top_grade_by_volume",
        "top_collection_days": "top_collection_days",
        "lowest_nonzero_member_contributor": "lowest_nonzero_member_contributor",
        "largest_parcel_by_product": "largest_parcel_by_product",
        "available_stock_gap": "available_stock_gap",
        "oldest_open_lot": "oldest_open_lot",
        "process_stage_loss_ranking": "process_stage_loss_ranking",
        "avg_paid_invoices_current_quarter": "avg_paid_invoices_current_quarter",
        "top_customer_by_orders": "top_customer_by_orders",
        "month_vs_month_charges": "month_vs_month_charges",
        "preharvest_status": "preharvest.get_parcel_preharvest_status",
        "parcel_status": "preharvest.get_parcel_preharvest_status",
        "parcels_list": "get_parcels_list",
        "batch_summary": "get_batch_summary",
    }
    for key, op in op_key_map.items():
        value = payload.get(key)
        if isinstance(value, list) and (value or key in {"invoices_summary", "commercial_orders", "commercial_totals", "finance_expenses"}):
            return op, f"SQLTools.{op}", len(value)
        if value is not None and not isinstance(value, list):
            return op, f"SQLTools.{op}", 1
    fallback_key, fallback_rows = _first_list_payload(payload, list(op_key_map.keys()))
    if fallback_key:
        op = op_key_map[fallback_key]
        return op, f"SQLTools.{op}", len(fallback_rows)
    if module:
        norm_module = re.sub(r"[^A-Z0-9]+", "_", str(module).upper()).strip("_") or "SQL"
        return f"UNSUPPORTED_{norm_module}_CAPABILITY", "SQLTools.unsupported", 0
    return None, None, 0


def _ensure_sql_dispatch_trace(
    *,
    payload: dict[str, Any],
    intent_family: str,
    route: Any,
    module: str,
    product: str | None,
    batch_ref: str | None,
    cooperative_id: Any,
    warnings: list[str],
) -> None:
    existing = payload.get("sql_dispatch_trace")
    if isinstance(existing, dict) and existing.get("sql_operation"):
        if "evidence_row_count" not in existing:
            existing["evidence_row_count"] = int(existing.get("row_count") or 0)
        if "tool_name" not in existing:
            existing["tool_name"] = existing.get("tool_function")
        if "module" not in existing:
            existing["module"] = module
        if "evidence_status" not in existing:
            existing["evidence_status"] = _derive_sql_evidence_status(trace=existing, warnings=warnings)
        payload["sql_dispatch_trace"] = existing
        return

    op, tool_name, row_count = _infer_sql_operation_from_payload(payload, module=module)
    payload["sql_dispatch_trace"] = {
        "intent_family": intent_family,
        "route": str(route.value if hasattr(route, "value") else route),
        "sql_operation": op or f"UNSUPPORTED_{_normalize_module_for_unsupported(module, normalized=_normalize_text(str(payload.get('query_text') or '')))}_CAPABILITY",
        "tool_name": tool_name or "SQLTools.unsupported",
        "tool_function": tool_name or "SQLTools.unsupported",
        "module": module,
        "cooperative_id": str(cooperative_id),
        "filters": {
            "product": product,
            "batch_ref": batch_ref,
            "module": module,
        },
        "row_count": int(row_count),
        "evidence_row_count": int(row_count),
        "evidence_type": "SQL",
        "evidence_status": EVIDENCE_HAS if int(row_count) > 0 else (EVIDENCE_UNSUPPORTED if str(op or "").startswith("UNSUPPORTED_") else EVIDENCE_NO_DATA),
        "warnings": sorted(set(warnings)),
    }


def _derive_sql_evidence_status(*, trace: dict[str, Any], warnings: list[str]) -> str:
    sql_operation = str(trace.get("sql_operation") or "").strip()
    row_count = int(trace.get("evidence_row_count") or trace.get("row_count") or 0)
    warning_set = {str(item or "").strip().upper() for item in warnings}
    if sql_operation.startswith("UNSUPPORTED_"):
        return EVIDENCE_UNSUPPORTED
    if any(
        code.startswith("SQL_TOOL_EXCEPTION")
        or code.endswith("_EXCEPTION")
        or code.endswith("_ERROR")
        or code.startswith("DB_")
        for code in warning_set
    ):
        return EVIDENCE_TOOL_ERROR
    if row_count > 0 and not {"SQL_DATA_INCOMPLETE", "INCOMPLETE_SQL_DATA"}.intersection(warning_set):
        return EVIDENCE_HAS
    if row_count > 0:
        return EVIDENCE_PARTIAL
    if sql_operation:
        return EVIDENCE_NO_DATA
    return EVIDENCE_PARTIAL


def _has_word(text: str, word: str) -> bool:
    return bool(re.search(rf"\\b{re.escape(word)}\\b", text))


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


def _extract_lot_refs(query: str, explicit: str | None = None) -> list[str]:
    refs: list[str] = []
    if explicit:
        refs.append(str(explicit).upper())
    matches = re.findall(r"\b(?:LOT|BATCH|MANG|MANGO|ARA|ARACH|MIL|BISS)[-_][A-Z0-9][A-Z0-9\-_]*\b", str(query or ""), flags=re.IGNORECASE)
    for item in matches:
        token = str(item or "").upper()
        if token not in refs:
            refs.append(token)
    return refs


def _is_operational_sql_query(normalized: str) -> bool:
    return any(
        token in normalized
        for token in (
            "stock",
            "lot",
            "lots",
            "post-recolte",
            "post recolte",
            "perte",
            "efficacite",
            "rendement",
            "entree",
            "sortie",
            "bilan",
            "etape",
            "tri",
            "sechage",
            "emballage",
            "transformation",
            "matiere",
            "kg",
        )
    )


def _build_sql_answer(payload: dict[str, Any]) -> str:
    if payload.get("stock_movements_journal") is not None:
        rows = payload.get("stock_movements_journal", [])
        if not rows:
            return "Aucun mouvement de stock correspondant n’a été trouvé."
        top = rows[0]
        return (
            f"Journal mouvements ({len(rows)}): dernier mouvement {top.get('movement_date')} | {top.get('movement_type')} / {top.get('action_type')} | "
            f"{float(top.get('quantity_kg', 0.0)):.1f} kg | source {top.get('source')} | "
            f"lot {top.get('batch_ref') or 'N/A'} | collecte {top.get('input_reference') or 'N/A'} | BL {top.get('bl_number') or 'N/A'}."
        )
    if payload.get("collecte_traceability_summary") is not None:
        rows = payload.get("collecte_traceability_summary", [])
        detailed_rows = payload.get("collecte_traceability", []) or []
        normalized_query = _normalize_text(str(payload.get("query_text") or ""))
        if rows:
            row = rows[0]
            needs_detail = any(token in normalized_query for token in ("membre", "producteur", "produit", "lot", "bl"))
            detail_line = ""
            if needs_detail and detailed_rows:
                top = detailed_rows[0]
                detail_line = (
                    f" Exemple récent: membre {top.get('member_name') or 'N/A'} | produit {top.get('product') or 'N/A'} | "
                    f"lot {top.get('batch_ref') or 'N/A'} | BL {top.get('bl_number') or 'N/A'}."
                )
            return (
                "Traçabilité collectes: "
                f"{int(row.get('total_inputs', 0))} collectes, "
                f"{int(row.get('with_bl_number', 0))} avec BL, "
                f"{int(row.get('with_justificatif', 0))} avec justificatif, "
                f"{int(row.get('linked_to_lot', 0))} liées à un lot. "
                "Politique stock: impact à la création de collecte, pas de duplication à la validation."
                + detail_line
            )
        return "Aucun enregistrement collecte correspondant n’a été trouvé."
    if payload.get("uploaded_files_evidence_summary") is not None:
        rows = payload.get("uploaded_files_evidence_summary", [])
        file_rows = payload.get("uploaded_files_evidence", []) or []
        normalized_query = _normalize_text(str(payload.get("query_text") or ""))
        if rows:
            row = rows[0]
            needs_file_detail = any(token in normalized_query for token in ("filename", "fichier", "file", "entity", "statut", "status", "lien"))
            detail_line = ""
            if needs_file_detail and file_rows:
                top = file_rows[0]
                detail_line = (
                    f" Dernier fichier: {top.get('filename') or 'N/A'} | type {top.get('entity_type') or 'N/A'} | "
                    f"entity_id {top.get('entity_id') or 'N/A'}."
                )
            return (
                "Preuves documentaires: "
                f"{int(row.get('uploaded_files_total', 0))} fichiers uploadés, "
                f"{int(row.get('collecte_with_justificatif', 0))} collectes avec justificatif, "
                f"{int(row.get('advance_with_devis', 0))} avances avec devis, "
                f"{int(row.get('treasury_with_justificatif', 0))} transactions trésorerie avec justificatif."
                + detail_line
            )
        return "Aucun fichier de preuve correspondant n’a été trouvé."
    if payload.get("farmer_advances_traceability_summary") is not None:
        rows = payload.get("farmer_advances_traceability_summary", [])
        detail_rows = payload.get("farmer_advances_traceability", []) or []
        normalized_query = _normalize_text(str(payload.get("query_text") or ""))
        if rows:
            row = rows[0]
            needs_detail = any(token in normalized_query for token in ("farmer", "producteur", "parcelle", "lot", "produit", "devis", "sync"))
            detail_line = ""
            if needs_detail and detail_rows:
                top = detail_rows[0]
                detail_line = (
                    f" Exemple: {top.get('member_name') or 'N/A'} | lot {top.get('batch_ref') or 'N/A'} | "
                    f"parcelle {top.get('parcel_name') or 'N/A'} | produit {top.get('product') or 'N/A'} | "
                    f"devis {'oui' if top.get('has_devis') else 'non'} | sync trésorerie {'oui' if top.get('treasury_synced') else 'non'}."
                )
            return (
                "Avances producteurs: "
                f"{int(row.get('advance_total', 0))} avances, "
                f"{int(row.get('with_devis', 0))} avec devis, "
                f"{int(row.get('with_treasury_sync', 0))} synchronisées trésorerie."
                + detail_line
            )
        return "Aucune avance producteur correspondante n’a été trouvée."
    if payload.get("treasury_traceability_summary") is not None:
        rows = payload.get("treasury_traceability_summary", [])
        detail_rows = payload.get("treasury_traceability", []) or []
        normalized_query = _normalize_text(str(payload.get("query_text") or ""))
        if rows:
            row = rows[0]
            needs_detail = any(token in normalized_query for token in ("receipt_reference", "reference", "source", "status", "statut"))
            detail_line = ""
            if needs_detail and detail_rows:
                top = detail_rows[0]
                detail_line = (
                    f" Exemple récent: ref {top.get('reference') or 'N/A'} | source {top.get('source_type') or 'N/A'} | "
                    f"receipt_reference {top.get('receipt_reference') or 'N/A'}."
                )
            return (
                "Trésorerie: "
                f"{int(row.get('missing_justificatif_count', 0))} transactions sans justificatif, "
                f"{int(row.get('enregistre_complet_count', 0))} ENREGISTRE_COMPLET, "
                f"{int(row.get('with_receipt_reference_count', 0))} avec receipt_reference, "
                f"{int(row.get('farmer_advance_linked_count', 0))} liées aux avances, "
                f"{int(row.get('commercial_invoice_income_linked_count', 0))} revenus liés aux factures commerciales."
                + detail_line
            )
        return "Aucune transaction trésorerie correspondante n’a été trouvée."
    if payload.get("commercial_invoice_linkage_summary") is not None:
        rows = payload.get("commercial_invoice_linkage_summary", [])
        detail_rows = payload.get("commercial_invoice_linkage", []) or []
        normalized_query = _normalize_text(str(payload.get("query_text") or ""))
        if rows:
            row = rows[0]
            needs_detail = any(token in normalized_query for token in ("receipt_reference", "source", "link", "lien", "invoice", "facture", "order", "commande"))
            detail_line = ""
            if needs_detail and detail_rows:
                top = detail_rows[0]
                detail_line = (
                    f" Exemple: commande {top.get('order_number') or 'N/A'} ({top.get('order_status') or 'N/A'}) | "
                    f"facture {top.get('invoice_number') or 'N/A'} ({top.get('invoice_status') or 'N/A'}) | "
                    f"treasury_ref {top.get('treasury_reference') or 'N/A'} | receipt_reference {top.get('receipt_reference') or 'N/A'}."
                )
            return (
                "Lien commercial/factures/trésorerie: "
                f"{int(row.get('linked_rows', 0))} lignes liées, "
                f"{int(row.get('paid_orders_with_invoice', 0))} commandes payées avec facture, "
                f"{int(row.get('paid_invoices_count', 0))} factures en statut payé, "
                f"{int(row.get('treasury_income_linked_count', 0))} revenus trésorerie liés à facture."
                + detail_line
            )
        return "Aucun lien commande/facture/trésorerie correspondant n’a été trouvé."
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
    if payload.get("stage_loss_analysis") is not None:
        rows = payload.get("stage_loss_analysis", [])
        if rows:
            top = rows[0]
            if top.get("batch_ref"):
                return (
                    f"Étape la plus critique pour {top.get('batch_ref')}: {top.get('stage_name')} | "
                    f"entrée {float(top.get('input_qty', 0.0) or 0.0):.1f} kg | "
                    f"sortie {float(top.get('output_qty', 0.0) or 0.0):.1f} kg | "
                    f"perte {float(top.get('loss_pct', 0.0) or 0.0):.1f}%."
                )
            return (
                f"Étape la moins efficace: {top.get('stage_name')} | "
                f"efficacité moyenne {float(top.get('efficiency_pct', 0.0) or 0.0):.1f}% | "
                f"perte moyenne {float(top.get('loss_pct', 0.0) or 0.0):.1f}%."
            )
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
        re.search(r"\b(membre|membres|producteur|producteurs|farmer|farmers)\b", str(payload.get("query_text", "")).lower())
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

    if payload.get("available_postharvest_lots"):
        items = payload["available_postharvest_lots"]
        if len(items) == 0:
            return "Aucun lot en post-récolte n'a été trouvé pour cette coopérative."
        elif len(items) == 1:
            item = items[0]
            return (
                f"Un lot post-récolte est disponible: {_display_batch_ref(item.get('batch_ref'))} "
                f"({item.get('product')}) avec {float(item.get('initial_qty', 0.0)):.1f} kg initial, "
                f"{float(item.get('current_qty', 0.0)):.1f} kg actuel."
            )
        lines = [f"Lots post-récolte disponibles ({len(items)}):"]
        for item in items[:15]:
            perte = float(item.get('loss_qty', 0.0))
            lines.append(
                f"- {_display_batch_ref(item.get('batch_ref'))}: {item.get('product')} | "
                f"{float(item.get('initial_qty', 0.0)):.1f} kg initial → {float(item.get('current_qty', 0.0)):.1f} kg | "
                f"perte {perte:.1f} kg | statut {item.get('status')}"
            )
        if len(items) > 15:
            lines.append(f"- … et {len(items) - 15} autres lot(s)")
        return "\n".join(lines)

    if payload.get("invoices_summary") is not None:
        grouped = payload.get("invoices_status_summary") or []
        normalized_query = _normalize_text(str(payload.get("query_text") or ""))
        if grouped and any(token in normalized_query for token in ("statut", "status", "regroupe", "regroup", "paiement")):
            if any(token in normalized_query for token in ("une seule", "uniquement", "seulement", "plus importante")):
                top = max(grouped, key=lambda row: float(row.get("total_amount_fcfa", 0.0) or 0.0))
                return f"Statut dominant des factures: {top.get('status')} ({int(top.get('count', 0))} facture(s), {float(top.get('total_amount_fcfa', 0.0)):.0f} FCFA)."
            return "Factures par statut: " + "; ".join(
                f"{row.get('status')} ({int(row.get('count', 0))}, {float(row.get('total_amount_fcfa', 0.0)):.0f} FCFA)"
                for row in grouped
            ) + "."
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
        grouped = payload.get("commercial_orders_status_summary") or []
        normalized_query = _normalize_text(str(payload.get("query_text") or ""))
        if grouped and any(token in normalized_query for token in ("statut", "status", "regroupe", "regroup")):
            if any(token in normalized_query for token in ("une seule", "uniquement", "seulement", "plus importante")):
                top = max(grouped, key=lambda row: float(row.get("total_amount_fcfa", 0.0) or 0.0))
                return f"Statut dominant des commandes: {top.get('status')} ({int(top.get('count', 0))} commande(s), {float(top.get('total_amount_fcfa', 0.0)):.0f} FCFA)."
            return "Commandes par statut: " + "; ".join(
                f"{row.get('status')} ({int(row.get('count', 0))}, {float(row.get('total_amount_fcfa', 0.0)):.0f} FCFA)"
                for row in grouped
            ) + "."
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
            f"entrée {float(item.get('input_quantity', item.get('input_qty', 0.0))):.1f} kg, "
            f"sortie {float(item.get('output_quantity', item.get('output_qty', 0.0))):.1f} kg, "
            f"perte {float(item.get('loss_percentage', item.get('loss_pct', 0.0))):.1f}%."
        )

    if payload.get("material_balance"):
        item = payload["material_balance"][0]
        return (
            f"Le bilan matière du lot {_display_batch_ref(item.get('batch_ref'))} montre une perte de "
            f"{float(item.get('loss_percentage', item.get('loss_pct', 0.0))):.1f} % et une efficacité de "
            f"{float(item.get('efficiency_percentage', item.get('efficiency_pct', 0.0))):.1f} %."
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
        in_kg = float(
            sum(
                float((row or {}).get("input_quantity", (row or {}).get("input_qty", 0.0)) or 0.0)
                for row in balance_rows
            )
        )
        out_kg = float(
            sum(
                float((row or {}).get("output_quantity", (row or {}).get("output_qty", 0.0)) or 0.0)
                for row in balance_rows
            )
        )
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
