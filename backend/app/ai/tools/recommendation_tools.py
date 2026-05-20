from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.ai.tools.app_data_tools import source, tool_response, warnings_for_empty
from app.models.batch import Batch
from app.models.enums import RiskLevel
from app.models.ml import MLRecommendationLog
from app.models.ml import MLPredictionLog
from app.models.product import Product
from app.models.process_step import ProcessStep
from app.models.rag import RAGChunk, RAGDocument
from app.models.recommendation import Recommendation
from app.models.stock import Stock
from app.models.user import User


class RecommendationTools:
    def __init__(self, db: Session | None = None, current_user: User | None = None):
        self.db = db
        self.current_user = current_user

    def build_recommendations(
        self,
        *,
        query: str,
        sql_results: dict[str, Any] | None,
        rag_results: list[dict[str, Any]] | None,
        ml_results: dict[str, Any] | None,
        detected_entities: dict,
    ) -> list[dict[str, Any]]:
        recommendations: list[dict[str, Any]] = []
        stage = _pick_first(detected_entities.get("stage"))
        product = _pick_first(detected_entities.get("product"))
        batch_ref = detected_entities.get("batch_ref")
        sql_payload = (sql_results or {}).get("data") if isinstance(sql_results, dict) else {}
        sql_sources = (sql_results or {}).get("sources") if isinstance(sql_results, dict) else []
        rag_sources = rag_results or []
        ml_payload = ml_results or {}
        ml_sources = ml_payload.get("sources") or []

        use_global_snapshot = _should_use_global_snapshot(query=query, detected_entities=detected_entities)
        snapshot = self._build_snapshot() if use_global_snapshot else {}
        scope_label = "GLOBAL_COOPERATIVE" if use_global_snapshot else "ACTIVE_QUERY"

        batch_rows = []
        if isinstance(sql_payload, dict):
            batch_rows = [row for row in (sql_payload.get("batch_summary") or []) if isinstance(row, dict)]
        if batch_ref:
            batch_rows = [row for row in batch_rows if str(row.get("batch_ref") or row.get("lot_code") or "").upper() == str(batch_ref).upper()] or batch_rows
        if product:
            batch_rows = [row for row in batch_rows if str(row.get("product") or "").lower() in _product_aliases(product)] or batch_rows
        batch_rows = sorted(batch_rows, key=lambda row: float(row.get("loss_pct", 0.0) or 0.0), reverse=True)

        if batch_rows:
            top = batch_rows[0]
            sql_ref = _sql_evidence_ref(
                label="SQL lot performance",
                short_fact=f"Lot {top.get('batch_ref') or top.get('lot_code')} perte {float(top.get('loss_pct', 0.0) or 0.0):.1f}% ; efficacité {float(top.get('efficiency_pct', 0.0) or 0.0):.1f}%",
                table="batches",
                batch_ref=top.get("batch_ref") or top.get("lot_code"),
                product=top.get("product"),
                metric_name="loss_pct",
                metric_value=float(top.get("loss_pct", 0.0) or 0.0),
            )
            recommendations.append(
                _recommendation_item(
                    rec_id="rec_sql_loss_priority",
                    title="Traiter immédiatement le lot le plus risqué",
                    action=f"Isoler le lot {top.get('batch_ref') or top.get('lot_code')} et renforcer le contrôle à l’étape critique.",
                    reason="Perte/efficacité opérationnelle défavorable observée dans les données SQL.",
                    priority="HIGH",
                    confidence=0.84,
                    related_batch=top.get("batch_ref") or top.get("lot_code"),
                    related_product=top.get("product"),
                    related_stage=top.get("critical_stage"),
                    evidence_refs=[sql_ref, _rule_evidence_ref("RULE_LOSS_PRIORITY_FROM_SQL", sql_ref)],
                    scope=scope_label,
                )
            )

        stage_rows = []
        if isinstance(sql_payload, dict):
            stage_rows = [row for row in (sql_payload.get("process_step_losses") or []) if isinstance(row, dict)]
        if stage:
            stage_rows = [row for row in stage_rows if str(row.get("stage") or "").lower() == str(stage).lower()] or stage_rows
        if stage_rows:
            top_stage = max(stage_rows, key=lambda row: float(row.get("loss_pct", 0.0) or 0.0))
            stage_ref = _sql_evidence_ref(
                label="SQL process loss",
                short_fact=f"Étape {top_stage.get('stage')} perte {float(top_stage.get('loss_pct', 0.0) or 0.0):.1f}%",
                table="process_steps",
                batch_ref=top_stage.get("batch_ref"),
                product=top_stage.get("product"),
                metric_name="loss_pct",
                metric_value=float(top_stage.get("loss_pct", 0.0) or 0.0),
            )
            recommendations.append(
                _recommendation_item(
                    rec_id="rec_sql_stage_control",
                    title="Sécuriser l’étape la plus pénalisante",
                    action=f"Standardiser les contrôles de {_stage_label(top_stage.get('stage'))} avec traçabilité entrée/sortie.",
                    reason="L’étape avec perte élevée doit être corrigée en priorité.",
                    priority="HIGH" if float(top_stage.get("loss_pct", 0.0) or 0.0) >= 12.0 else "MEDIUM",
                    confidence=0.78,
                    related_batch=top_stage.get("batch_ref"),
                    related_product=top_stage.get("product"),
                    related_stage=top_stage.get("stage"),
                    evidence_refs=[stage_ref, _rule_evidence_ref("RULE_STAGE_CONTROL_FROM_SQL", stage_ref)],
                    scope=scope_label,
                )
            )

        stock_rows = []
        if isinstance(sql_payload, dict):
            stock_rows = [row for row in (sql_payload.get("current_stock") or []) if isinstance(row, dict)]
        low_stock_rows = [row for row in stock_rows if bool(row.get("is_low"))]
        if low_stock_rows:
            stock = low_stock_rows[0]
            stock_ref = _sql_evidence_ref(
                label="SQL stock threshold",
                short_fact=f"Produit {stock.get('product')} disponible {float(stock.get('available_stock_kg', 0.0) or 0.0):.1f} kg, seuil {float(stock.get('threshold_kg', 0.0) or 0.0):.1f} kg",
                table="stocks",
                product=stock.get("product"),
                metric_name="available_stock_kg",
                metric_value=float(stock.get("available_stock_kg", 0.0) or 0.0),
            )
            recommendations.append(
                _recommendation_item(
                    rec_id="rec_sql_stock_replenish",
                    title="Prévenir les ruptures de stock",
                    action=f"Lancer un réapprovisionnement ciblé sur {stock.get('product')} et réserver un stock de sécurité.",
                    reason="Le stock net est sous le seuil opérationnel.",
                    priority="MEDIUM",
                    confidence=0.72,
                    related_product=stock.get("product"),
                    related_stage="stockage",
                    evidence_refs=[stock_ref, _rule_evidence_ref("RULE_STOCK_GAP_FROM_SQL", stock_ref)],
                    scope=scope_label,
                )
            )

        ml_risk = str(ml_payload.get("risk_level") or "").upper()
        ml_conf = float(ml_payload.get("confidence", 0.0) or 0.0)
        if ml_risk in {"HIGH", "MEDIUM"} and ml_sources:
            ml_source = ml_sources[0]
            ml_ref = _ml_evidence_ref(
                label="ML risk signal",
                short_fact=f"Signal ML {ml_risk} sur lot {ml_payload.get('affected_batch') or 'N/A'}",
                model=str(ml_source.get("model") or "ml_prediction_logs"),
                ml_log_id=ml_source.get("result_id"),
                batch_ref=ml_payload.get("affected_batch"),
                metric_name="risk_level",
                metric_value=ml_risk,
            )
            recommendations.append(
                _recommendation_item(
                    rec_id="rec_ml_preventive_review",
                    title="Exécuter une revue préventive pilotée par signal ML",
                    action="Déclencher une revue lot-étape sous 24h et prioriser les contrôles des flux à risque.",
                    reason=f"Le signal ML indique un risque {ml_risk}.",
                    priority="HIGH" if ml_risk == "HIGH" else "MEDIUM",
                    confidence=min(0.82, max(0.55, ml_conf)),
                    related_batch=ml_payload.get("affected_batch"),
                    related_product=product,
                    related_stage=ml_payload.get("affected_stage"),
                    evidence_refs=[ml_ref, _rule_evidence_ref("RULE_PREVENTIVE_REVIEW_FROM_ML", ml_ref)],
                    scope=scope_label,
                )
            )

        if rag_sources:
            rag_source = rag_sources[0]
            rag_ref = _rag_evidence_ref(
                label="RAG best-practice",
                short_fact=f"Contexte pratique: {str(rag_source.get('title') or 'source documentaire')}",
                title=rag_source.get("title"),
                chunk_id=rag_source.get("chunk_id"),
                source_id=rag_source.get("document_id"),
            )
            recommendations.append(
                _recommendation_item(
                    rec_id="rec_rag_practice",
                    title="Appliquer les bonnes pratiques documentées",
                    action="Appliquer la check-list de séchage/tri/emballage et tracer les écarts sur le prochain cycle.",
                    reason="Le corpus documentaire fournit un protocole directement applicable.",
                    priority="MEDIUM",
                    confidence=0.66,
                    related_product=product,
                    related_stage=stage,
                    evidence_refs=[rag_ref],
                    scope=scope_label,
                )
            )

        if use_global_snapshot and snapshot:
            global_rows = snapshot.get("high_risk_lots", [])
            if global_rows:
                top = global_rows[0]
                gref = _sql_evidence_ref(
                    label="SQL global lot risk snapshot",
                    short_fact=f"Global coop: lot {top.get('batch_ref')} perte {float(top.get('loss_pct', 0.0) or 0.0):.1f}%",
                    table="batches",
                    batch_ref=top.get("batch_ref"),
                    product=top.get("product"),
                    metric_name="loss_pct",
                    metric_value=float(top.get("loss_pct", 0.0) or 0.0),
                )
                recommendations.append(
                    _recommendation_item(
                        rec_id="rec_global_coop_priority",
                        title="Prioriser le lot critique au niveau coopérative",
                        action=f"Prioriser une revue opérationnelle du lot {top.get('batch_ref')} à l’échelle coopérative.",
                        reason="Synthèse globale coopérative demandée.",
                        priority="HIGH",
                        confidence=0.7,
                        related_batch=top.get("batch_ref"),
                        related_product=top.get("product"),
                        evidence_refs=[gref, _rule_evidence_ref("RULE_GLOBAL_COOP_PRIORITY", gref)],
                        scope="GLOBAL_COOPERATIVE",
                    )
                )

        recommendations = _dedupe_recommendations(recommendations)
        return recommendations[:5]

    def _build_snapshot(self) -> dict[str, Any]:
        if self.db is None or self.current_user is None:
            return {
                "high_risk_lots": [],
                "low_efficiency_lots": [],
                "stage_losses": [],
                "low_stocks": [],
                "ml_signals": [],
                "rag_practices": [],
                "batch_count": 0,
            }

        cooperative_id = self.current_user.cooperative_id

        # Batches risk/efficiency
        batch_rows = self.db.execute(
            select(Batch.code, Product.name, Batch.initial_qty, Batch.current_qty)
            .join(Product, Product.id == Batch.product_id)
            .where(Batch.cooperative_id == cooperative_id)
            .order_by(Batch.creation_date.desc())
        ).all()
        lot_metrics: list[dict[str, Any]] = []
        for code, product_name, initial_qty, current_qty in batch_rows:
            initial = float(initial_qty or 0.0)
            current = float(current_qty or 0.0)
            if initial <= 0:
                continue
            loss_pct = ((initial - current) / initial) * 100.0
            eff_pct = (current / initial) * 100.0
            lot_metrics.append(
                {
                    "batch_ref": str(code),
                    "product": str(product_name),
                    "loss_pct": loss_pct,
                    "efficiency_pct": eff_pct,
                    "critical_stage": "séchage" if loss_pct >= 12.0 else None,
                }
            )
        high_risk_lots = sorted(
            [item for item in lot_metrics if float(item.get("loss_pct", 0.0)) >= 12.0 or float(item.get("efficiency_pct", 100.0)) <= 85.0],
            key=lambda row: float(row.get("loss_pct", 0.0)),
            reverse=True,
        )[:5]
        low_efficiency_lots = sorted(
            [item for item in lot_metrics if float(item.get("efficiency_pct", 100.0)) < 85.0],
            key=lambda row: float(row.get("efficiency_pct", 100.0)),
        )[:5]

        # Process stages with highest average loss
        step_rows = self.db.execute(
            select(ProcessStep.type, ProcessStep.qty_in, ProcessStep.qty_out)
            .join(Batch, Batch.id == ProcessStep.batch_id)
            .where(Batch.cooperative_id == cooperative_id)
        ).all()
        stage_buckets: dict[str, dict[str, float]] = {}
        for step_type, qty_in, qty_out in step_rows:
            q_in = float(qty_in or 0.0)
            q_out = float(qty_out or 0.0)
            if q_in <= 0:
                continue
            loss_pct = ((q_in - q_out) / q_in) * 100.0
            key = str(step_type or "").strip() or "inconnu"
            bucket = stage_buckets.setdefault(key, {"loss_sum": 0.0, "count": 0.0})
            bucket["loss_sum"] += loss_pct
            bucket["count"] += 1.0
        stage_losses = []
        for key, value in stage_buckets.items():
            if value["count"] <= 0:
                continue
            stage_losses.append(
                {
                    "stage": key,
                    "avg_loss_pct": value["loss_sum"] / value["count"],
                    "batch_ref": high_risk_lots[0].get("batch_ref") if high_risk_lots else None,
                    "product": high_risk_lots[0].get("product") if high_risk_lots else None,
                }
            )
        stage_losses.sort(key=lambda row: float(row.get("avg_loss_pct", 0.0)), reverse=True)

        # Stock alerts
        stock_rows = self.db.execute(
            select(Product.name, Stock.total_stock_kg, Stock.reserved_in_lots_kg, Stock.threshold)
            .join(Product, Product.id == Stock.product_id)
            .where(Stock.cooperative_id == cooperative_id)
        ).all()
        low_stocks = []
        for product_name, total_stock_kg, reserved_in_lots_kg, threshold in stock_rows:
            available = float(total_stock_kg or 0.0) - float(reserved_in_lots_kg or 0.0)
            th = float(threshold or 0.0)
            if available <= th:
                low_stocks.append(
                    {
                        "product": str(product_name),
                        "available_kg": available,
                        "threshold_kg": th,
                    }
                )
        low_stocks.sort(key=lambda row: float(row.get("available_kg", 0.0)))

        # ML risk logs
        ml_rows = self.db.execute(
            select(MLPredictionLog.batch_id, MLPredictionLog.product, MLPredictionLog.critical_stage, MLPredictionLog.risk_level, MLPredictionLog.predicted_loss_pct)
            .where(MLPredictionLog.risk_level.in_([RiskLevel.HIGH, RiskLevel.MEDIUM]))
            .order_by(MLPredictionLog.created_at.desc())
            .limit(5)
        ).all()
        batch_ref_by_id = {str(row_id): code for row_id, code in self.db.execute(select(Batch.id, Batch.code).where(Batch.cooperative_id == cooperative_id)).all()}
        ml_signals = [
            {
                "batch_ref": batch_ref_by_id.get(str(batch_id), None) if batch_id else None,
                "product": str(product_name or ""),
                "critical_stage": str(critical_stage or ""),
                "risk_level": str(risk_level.value if hasattr(risk_level, "value") else risk_level or ""),
                "predicted_loss_pct": float(predicted_loss_pct or 0.0),
            }
            for batch_id, product_name, critical_stage, risk_level, predicted_loss_pct in ml_rows
        ]

        # RAG best-practice snippets
        rag_rows = self.db.execute(
            select(RAGDocument.title, RAGChunk.content)
            .join(RAGChunk, RAGChunk.document_id == RAGDocument.id)
            .where(
                RAGChunk.cooperative_id == cooperative_id,
                or_(
                    func.lower(RAGChunk.content).like("%séchage%"),
                    func.lower(RAGChunk.content).like("%sechage%"),
                    func.lower(RAGChunk.content).like("%tri%"),
                    func.lower(RAGChunk.content).like("%humid%"),
                    func.lower(RAGChunk.content).like("%stockage%"),
                ),
            )
            .limit(3)
        ).all()
        rag_practices = [
            {
                "title": str(title or "Bonnes pratiques"),
                "snippet": _compact_text(str(content or ""), 240),
                "stage": "séchage/tri",
            }
            for title, content in rag_rows
            if str(content or "").strip()
        ]

        return {
            "high_risk_lots": high_risk_lots,
            "low_efficiency_lots": low_efficiency_lots,
            "stage_losses": stage_losses[:5],
            "low_stocks": low_stocks[:5],
            "ml_signals": ml_signals,
            "rag_practices": rag_practices,
            "batch_count": len(lot_metrics),
        }

    def get_ai_recommendations(
        self,
        scope: str | None = None,
        entity_id: str | None = None,
        product: str | None = None,
        stage: str | None = None,
        priority: str | None = None,
    ) -> dict[str, Any]:
        if self.db is None or self.current_user is None:
            return tool_response(ok=False, data=None, sources=[], warnings=["Ce module n’est pas encore disponible dans les données."])
        rows = self.db.execute(
            select(Recommendation, Batch, Product)
            .join(Batch, Batch.id == Recommendation.batch_id)
            .join(Product, Product.id == Batch.product_id)
            .where(Batch.cooperative_id == self.current_user.cooperative_id)
            .order_by(Recommendation.created_at.desc())
            .limit(30)
        ).all()
        data = []
        for recommendation, batch, product_row in rows:
            if product and str(product_row.name).lower() not in _product_aliases(product):
                continue
            data.append(_recommendation_payload(recommendation, batch, product_row))
        return tool_response(ok=True, data=data, sources=[source(table="recommendations,batches", label="Recommandations IA", record_count=len(data))], warnings=warnings_for_empty(data))

    def get_recommendations_for_batch(self, batch_ref: str) -> dict[str, Any]:
        if self.db is None or self.current_user is None:
            return tool_response(ok=False, data=None, sources=[], warnings=["Ce module n’est pas encore disponible dans les données."])
        rows = self.db.execute(
            select(Recommendation, Batch, Product)
            .join(Batch, Batch.id == Recommendation.batch_id)
            .join(Product, Product.id == Batch.product_id)
            .where(Batch.cooperative_id == self.current_user.cooperative_id, Batch.code.ilike(batch_ref))
            .order_by(Recommendation.created_at.desc())
        ).all()
        data = [_recommendation_payload(recommendation, batch, product) for recommendation, batch, product in rows]
        warnings = warnings_for_empty(data)
        if not data:
            warnings = [f"Aucune recommandation n’a été trouvée pour le lot {batch_ref}."]
        return tool_response(ok=True, data=data, sources=[source(table="recommendations,batches", label="Recommandations du lot", record_count=len(data), related_batch=batch_ref)], warnings=warnings)

    def get_recommendations_for_parcel(self, parcel_id: str) -> dict[str, Any]:
        return tool_response(ok=False, data=None, sources=[], warnings=["Ce module n’est pas encore disponible dans les données."])

    def get_top_recommendations(self, limit: int = 5) -> dict[str, Any]:
        if self.db is None or self.current_user is None:
            return tool_response(ok=False, data=None, sources=[], warnings=["Ce module n’est pas encore disponible dans les données."])
        rows = self.db.scalars(select(MLRecommendationLog).order_by(MLRecommendationLog.created_at.desc()).limit(max(1, min(int(limit or 5), 20)))).all()
        data = [
            {
                "recommendation_log_id": str(row.id),
                "batch_id": str(row.batch_id) if row.batch_id else None,
                "recommendation": row.structured_recommendation,
                "created_at": str(row.created_at),
            }
            for row in rows
        ]
        return tool_response(ok=True, data=data, sources=[source(table="ml_recommendation_logs", label="Recommandations récentes", record_count=len(data))], warnings=warnings_for_empty(data))


def _collect_evidence(*, sql_results: dict[str, Any] | None, rag_results: list[dict[str, Any]] | None, ml_results: dict[str, Any] | None) -> list[str]:
    evidence: list[str] = []
    if sql_results and sql_results.get("sources"):
        for source in sql_results.get("sources", [])[:2]:
            evidence.append(f"SQL: {source.get('table')} ({source.get('label')})")
    if rag_results:
        for source in rag_results[:2]:
            evidence.append(f"RAG: {source.get('title')}")
    if ml_results and ml_results.get("sources"):
        for source in ml_results.get("sources", [])[:1]:
            evidence.append(f"ML: {source.get('model')}")
    return evidence


def _recommendation_item(
    *,
    rec_id: str,
    title: str,
    action: str,
    reason: str,
    priority: str,
    confidence: float,
    evidence_refs: list[dict[str, Any]],
    scope: str,
    related_batch: str | None = None,
    related_product: str | None = None,
    related_stage: str | None = None,
) -> dict[str, Any]:
    return {
        "id": rec_id,
        "title": title,
        "action": action,
        "reason": reason,
        "priority": str(priority or "MEDIUM").upper(),
        "confidence": float(confidence),
        "severity": str(priority or "MEDIUM").upper(),
        "scope": scope,
        "related_batch": related_batch,
        "related_product": related_product,
        "related_stage": related_stage,
        "evidence_refs": [ref for ref in evidence_refs if isinstance(ref, dict)],
    }


def _sql_evidence_ref(
    *,
    label: str,
    short_fact: str,
    table: str,
    batch_ref: str | None = None,
    product: str | None = None,
    metric_name: str | None = None,
    metric_value: float | str | None = None,
) -> dict[str, Any]:
    source_id = f"sql:{table}:{batch_ref or product or metric_name or 'fact'}"
    return {
        "type": "SQL",
        "source_id": source_id,
        "label": label,
        "short_fact": short_fact,
        "table": table,
        "batch_ref": batch_ref,
        "metric_name": metric_name,
        "metric_value": metric_value,
    }


def _rag_evidence_ref(
    *,
    label: str,
    short_fact: str,
    title: str | None,
    chunk_id: str | None,
    source_id: str | None,
) -> dict[str, Any]:
    return {
        "type": "RAG",
        "source_id": source_id or f"rag:{chunk_id or 'chunk'}",
        "label": label,
        "short_fact": short_fact,
        "chunk_id": chunk_id,
        "source_title": title,
    }


def _ml_evidence_ref(
    *,
    label: str,
    short_fact: str,
    model: str,
    ml_log_id: str | None,
    batch_ref: str | None,
    metric_name: str | None = None,
    metric_value: str | float | None = None,
) -> dict[str, Any]:
    return {
        "type": "ML",
        "source_id": f"ml:{ml_log_id or model}",
        "label": label,
        "short_fact": short_fact,
        "ml_log_id": ml_log_id,
        "batch_ref": batch_ref,
        "metric_name": metric_name,
        "metric_value": metric_value,
    }


def _rule_evidence_ref(rule_name: str, triggering_ref: dict[str, Any]) -> dict[str, Any]:
    base_type = str(triggering_ref.get("type") or "SQL")
    source_id = str(triggering_ref.get("source_id") or f"rule:{rule_name}")
    return {
        "type": "RULE",
        "source_id": f"rule:{rule_name}",
        "label": f"Rule {rule_name}",
        "short_fact": f"Rule {rule_name} déclenchée à partir de {base_type}:{source_id}",
        "rule_name": rule_name,
        "triggered_by_type": base_type,
        "triggered_by_source_id": source_id,
    }


def _should_use_global_snapshot(*, query: str, detected_entities: dict[str, Any]) -> bool:
    lowered = str(query or "").lower()
    has_specific_entity = bool(detected_entities.get("batch_ref") or detected_entities.get("product") or detected_entities.get("stage"))
    asks_global = any(
        token in lowered
        for token in (
            "coopérative",
            "cooperative",
            "global",
            "ensemble de la coop",
            "toute la coop",
            "au niveau coop",
            "vue globale",
        )
    )
    return asks_global and not has_specific_entity


def _pick_first(values):
    if isinstance(values, list) and values:
        return values[0]
    return None


def _recommendation_payload(recommendation: Recommendation, batch: Batch, product: Product) -> dict[str, Any]:
    return {
        "recommendation_id": str(recommendation.id),
        "batch_ref": batch.code,
        "product": product.name,
        "loss_pct": float(recommendation.loss_pct or 0.0),
        "efficiency_pct": float(recommendation.efficiency_pct or 0.0),
        "risk_level": str(recommendation.risk_level.value if hasattr(recommendation.risk_level, "value") else recommendation.risk_level),
        "suggested_action": recommendation.suggested_action,
        "rationale": recommendation.rationale,
        "created_at": str(recommendation.created_at),
    }


def _product_aliases(value: str | None) -> list[str]:
    raw = str(value or "").strip().lower()
    if raw in {"mangue", "mango"}:
        return ["mangue", "mango"]
    if raw in {"arachide", "peanut"}:
        return ["arachide", "peanut"]
    if raw in {"mil", "millet"}:
        return ["mil", "millet"]
    return [raw]


def _stage_label(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "drying": "séchage",
        "sechage": "séchage",
        "séchage": "séchage",
        "sorting": "tri",
        "tri": "tri",
        "cleaning": "nettoyage",
        "nettoyage": "nettoyage",
        "packaging": "emballage",
        "conditionnement": "emballage",
        "storage": "stockage",
    }
    return mapping.get(raw, str(value or "étape critique"))


def _build_rag_action(snippet: str) -> str:
    text = str(snippet or "").strip()
    if not text:
        return "Appliquer un protocole standard de séchage/tri avec contrôle humidité et qualité visuelle."
    lowered = text.lower()
    if "humid" in lowered:
        return "Mettre un contrôle d’humidité systématique avant et après séchage, puis valider au tri."
    if "tri" in lowered:
        return "Renforcer le tri en entrée et sortie de process avec critères de qualité standardisés."
    return "Appliquer les pratiques documentées de séchage/tri et tracer les écarts par lot."


def _dedupe_recommendations(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        action = str(item.get("action") or "").strip().lower()
        key = "|".join(
            [
                str(item.get("priority") or "").upper(),
                action,
                str(item.get("related_batch") or ""),
                str(item.get("related_product") or ""),
                str(item.get("related_stage") or ""),
            ]
        )
        if not action or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    priority_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    deduped.sort(key=lambda rec: (priority_rank.get(str(rec.get("priority") or "").upper(), 9), -float(rec.get("confidence", 0.0) or 0.0)))
    return deduped


def _compact_text(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."
