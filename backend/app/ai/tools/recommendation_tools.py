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

        base_evidence = _collect_evidence(sql_results=sql_results, rag_results=rag_results, ml_results=ml_results)
        snapshot = self._build_snapshot()

        # 1) Lots à risque élevé / faible efficacité
        high_risk = snapshot.get("high_risk_lots", [])
        if high_risk:
            item = high_risk[0]
            recommendations.append(
                {
                    "title": "Traiter immédiatement le lot le plus risqué",
                    "priority": "HIGH",
                    "related_batch": item.get("batch_ref"),
                    "related_product": item.get("product"),
                    "related_stage": item.get("critical_stage"),
                    "reason": (
                        f"Perte élevée ({float(item.get('loss_pct', 0.0)):.1f}%) et efficacité faible "
                        f"({float(item.get('efficiency_pct', 0.0)):.1f}%) sur le lot ciblé."
                    ),
                    "action": (
                        f"Isoler le lot {item.get('batch_ref')}, renforcer le contrôle au "
                        f"{_stage_label(item.get('critical_stage'))}, puis reclasser les intrants dégradés."
                    ),
                    "evidence": [
                        *base_evidence,
                        f"SQL: batches (lot {item.get('batch_ref')} perte {float(item.get('loss_pct', 0.0)):.1f}% ; efficacité {float(item.get('efficiency_pct', 0.0)):.1f}%)",
                    ],
                    "expected_impact": "Réduction rapide des pertes sur les lots critiques.",
                    "confidence": 0.86,
                }
            )

        low_efficiency = snapshot.get("low_efficiency_lots", [])
        if low_efficiency:
            item = low_efficiency[0]
            recommendations.append(
                {
                    "title": "Corriger les écarts de rendement des lots faibles",
                    "priority": "HIGH" if float(item.get("efficiency_pct", 100.0) or 100.0) < 75.0 else "MEDIUM",
                    "related_batch": item.get("batch_ref"),
                    "related_product": item.get("product"),
                    "related_stage": item.get("critical_stage"),
                    "reason": f"Efficacité en dessous de la cible ({float(item.get('efficiency_pct', 0.0)):.1f}%).",
                    "action": (
                        f"Mettre en place un contrôle d’entrée/sortie au niveau du lot {item.get('batch_ref')} "
                        "et ajuster le temps de traitement de l’étape critique."
                    ),
                    "evidence": [
                        f"SQL: batches (lot {item.get('batch_ref')} efficacité {float(item.get('efficiency_pct', 0.0)):.1f}% ; perte {float(item.get('loss_pct', 0.0)):.1f}%)"
                    ],
                    "expected_impact": "Amélioration du rendement matière par lot.",
                    "confidence": 0.8,
                }
            )

        # 2) Étapes process avec pertes élevées
        stage_losses = snapshot.get("stage_losses", [])
        if stage_losses:
            top_stage = stage_losses[0]
            recommendations.append(
                {
                    "title": "Sécuriser l’étape de process la plus coûteuse",
                    "priority": "HIGH" if float(top_stage.get("avg_loss_pct", 0.0) or 0.0) >= 15.0 else "MEDIUM",
                    "related_batch": top_stage.get("batch_ref"),
                    "related_product": top_stage.get("product"),
                    "related_stage": top_stage.get("stage"),
                    "reason": (
                        f"L’étape {_stage_label(top_stage.get('stage'))} concentre les pertes "
                        f"({float(top_stage.get('avg_loss_pct', 0.0)):.1f}% en moyenne)."
                    ),
                    "action": (
                        f"Standardiser les contrôles de {_stage_label(top_stage.get('stage'))} "
                        "avec seuils humidité/tri et feuille de suivi par lot."
                    ),
                    "evidence": [
                        f"SQL: process_steps (étape {top_stage.get('stage')} perte moyenne {float(top_stage.get('avg_loss_pct', 0.0)):.1f}%)"
                    ],
                    "expected_impact": "Réduction structurelle des pertes au poste critique.",
                    "confidence": 0.78,
                }
            )

        # 3) Niveaux de stocks critiques
        low_stocks = snapshot.get("low_stocks", [])
        if low_stocks:
            stock = low_stocks[0]
            recommendations.append(
                {
                    "title": "Prévenir les ruptures de stock opérationnelles",
                    "priority": "MEDIUM",
                    "related_batch": None,
                    "related_product": stock.get("product"),
                    "related_stage": "stockage",
                    "reason": (
                        f"Stock disponible faible pour {stock.get('product')} "
                        f"({float(stock.get('available_kg', 0.0)):.1f} kg, seuil {float(stock.get('threshold_kg', 0.0)):.1f} kg)."
                    ),
                    "action": (
                        f"Lancer un réapprovisionnement ciblé sur {stock.get('product')} "
                        "et réserver un minimum de sécurité pour les lots en cours."
                    ),
                    "evidence": [
                        f"SQL: stocks ({stock.get('product')} disponible {float(stock.get('available_kg', 0.0)):.1f} kg ; seuil {float(stock.get('threshold_kg', 0.0)):.1f} kg)"
                    ],
                    "expected_impact": "Réduction des interruptions et des arbitrages de dernière minute.",
                    "confidence": 0.71,
                }
            )

        # 4) Signaux ML (si disponibles)
        ml_risk = (ml_results or {}).get("risk_level")
        observed_loss = (ml_results or {}).get("observed_loss_pct")
        ml_signals = snapshot.get("ml_signals", [])
        if ml_risk in {"HIGH", "MEDIUM"} or ml_signals:
            top_signal = ml_signals[0] if ml_signals else {}
            signal_level = str(ml_risk or top_signal.get("risk_level") or "MEDIUM").upper()
            recommendations.append(
                {
                    "title": "Exécuter un plan d’action préventif piloté par signal ML",
                    "priority": "HIGH" if signal_level == "HIGH" else "MEDIUM",
                    "related_batch": (ml_results or {}).get("affected_batch") or top_signal.get("batch_ref"),
                    "related_product": product or top_signal.get("product"),
                    "related_stage": (ml_results or {}).get("affected_stage") or top_signal.get("critical_stage"),
                    "reason": (
                        f"Le signal ML indique un risque {signal_level}"
                        + (f" avec perte observée {float(observed_loss):.1f}%." if observed_loss is not None else ".")
                    ),
                    "action": "Déclencher une revue lot-étape sous 24h et prioriser les contrôles sur les flux à risque.",
                    "evidence": [
                        *base_evidence,
                        *(
                            [
                                f"ML: ml_prediction_logs ({top_signal.get('batch_ref') or 'batch inconnu'} risque {top_signal.get('risk_level')})"
                            ]
                            if top_signal
                            else []
                        ),
                    ],
                    "expected_impact": "Réduction des pertes inattendues et anticipation des dérives.",
                    "confidence": 0.74,
                }
            )

        # 5) Bonnes pratiques RAG
        rag_practices = snapshot.get("rag_practices", [])
        if rag_practices:
            rag_item = rag_practices[0]
            recommendations.append(
                {
                    "title": "Appliquer les bonnes pratiques documentées",
                    "priority": "MEDIUM",
                    "related_batch": None,
                    "related_product": product,
                    "related_stage": stage or rag_item.get("stage"),
                    "reason": "Le corpus RAG fournit des pratiques directement applicables à la réduction des pertes.",
                    "action": _build_rag_action(rag_item.get("snippet") or ""),
                    "evidence": [f"RAG: {rag_item.get('title') or 'Source post-récolte'}"],
                    "expected_impact": "Standardisation des opérations selon des pratiques validées.",
                    "confidence": 0.68,
                }
            )

        recommendations = _dedupe_recommendations(recommendations)

        if recommendations:
            return recommendations[:5]

        # Fallback grounded minimal action using available SQL footprint
        if snapshot.get("batch_count", 0) > 0:
            return [
                {
                    "title": "Mettre en place un suivi hebdomadaire des pertes",
                    "priority": "MEDIUM",
                    "related_batch": None,
                    "related_product": product,
                    "related_stage": stage,
                    "reason": "Des lots actifs existent, mais les signaux détaillés restent limités.",
                    "action": "Créer une revue hebdomadaire par lot (entrée/sortie/perte) avec seuil d’alerte à 12%.",
                    "evidence": [f"SQL: batches ({int(snapshot.get('batch_count', 0))} lot(s) suivis)"],
                    "expected_impact": "Amélioration progressive de la détection précoce des pertes.",
                    "confidence": 0.6,
                }
            ]

        return []

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
