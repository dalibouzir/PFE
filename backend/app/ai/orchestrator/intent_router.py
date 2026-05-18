from __future__ import annotations

import re
import unicodedata

from app.ai.orchestrator.agent_types import IntentRouteDecision
from app.ai.orchestrator.entity_extractor import EntityExtractor
from app.ai.orchestrator.module_registry import ModuleRegistry
from app.ai.schemas.agent_schemas import AgentRoute

PRODUCT_MAP = {
    "mangue": "mango",
    "mango": "mango",
    "arachide": "peanut",
    "peanut": "peanut",
    "mil": "millet",
    "millet": "millet",
    "bissap": "bissap",
}
STAGE_MAP = {
    "nettoyage": "cleaning",
    "cleaning": "cleaning",
    "sechage": "drying",
    "séchage": "drying",
    "drying": "drying",
    "tri": "sorting",
    "sorting": "sorting",
    "emballage": "packaging",
    "packaging": "packaging",
    "conditionnement": "packaging",
    "storage": "storage",
    "stockage": "storage",
}
SMALL_TALK = {"bonjour", "salut", "hello", "hi", "bonsoir", "ok", "merci", "coucou", "ca va", "ça va"}
OUT_SCOPE = {"champions league", "football", "nba", "bitcoin", "weather", "météo", "movie", "film"}
UNSUPPORTED_FORECAST_HINTS = {
    "predis",
    "prédis",
    "predire",
    "prédire",
    "precis",
    "précis",
    "précisément",
    "precisement",
    "exactement le prix",
    "prix de vente du mois prochain",
    "mois prochain",
    "prochain mois",
    "tomorrow weather",
}
UNSUPPORTED_HR_SUBJECTIVE_HINTS = {
    "licencier",
    "licencie",
    "licenciement",
    "virer",
    "renvoyer",
    "plus fiable",
    "moins fiable",
    "fiable",
    "performance humaine",
    "ressources humaines",
    "rh",
}
RECO_HINTS = {
    "recommand",
    "actions prioritaires",
    "action prioritaire",
    "que faire",
    "on devrait faire quoi",
    "que doit on faire",
    "que doit-on faire",
    "plan d'action",
    "action plan",
    "actions concretes",
    "actions concrètes",
    "comment réduire",
    "comment reduire",
    "comment améliorer",
    "comment ameliorer",
    "mieux secher",
    "mieux sécher",
    "plan contre",
    "faut il faire",
    "faut-il faire",
    "quoi faire concretement",
    "quoi faire concrètement",
}
RECOMMENDATION_REGEXES = (
    re.compile(r"\bconseill\w*\b", re.IGNORECASE),
    re.compile(r"\bque\s+faire\b", re.IGNORECASE),
    re.compile(r"\bon\s+devrait\s+faire\s+quoi\b", re.IGNORECASE),
    re.compile(r"\bactions?\s+priorit\w*\b", re.IGNORECASE),
    re.compile(r"\bplan\s+d[' ]action\b", re.IGNORECASE),
    re.compile(r"\bcomment\b.{0,24}\b(am[eé]lior\w*|r[eé]duir\w*)\b", re.IGNORECASE),
    re.compile(r"\bmieux\s+s[eé]ch\w*\b", re.IGNORECASE),
)
RISK_HINTS = {"risque", "risk", "anomal", "prédiction", "prediction"}
EXPLANATION_HINTS = {
    "explique",
    "explain",
    "pourquoi",
    "why",
    "cause",
    "bonnes pratiques",
    "best practices",
    "comment réduire",
    "comment reduire",
    "comment ameliorer",
    "comment améliorer",
    "mieux secher",
    "mieux sécher",
    "meilleures pratiques",
    "références",
    "references",
    "humidite",
    "humidité",
    "stockage",
    "check-list",
    "checklist",
    "conseils",
    "conseil",
    "que faire",
}
BEST_PRACTICE_HINTS = {
    "bonnes pratiques",
    "meilleures pratiques",
    "best practices",
    "références",
    "references",
    "comment réduire",
    "comment reduire",
    "comment ameliorer",
    "comment améliorer",
    "mieux secher",
    "mieux sécher",
    "humidite",
    "humidité",
    "stockage",
    "check-list",
    "checklist",
    "casse",
    "procedure",
    "procédure",
    "pratiques post-récolte",
    "pratiques post recolte",
    "conseils de manipulation",
    "manipulation",
    "conseils de séchage",
    "conseils de sechage",
    "conseils",
    "que faire",
    "pratiques opérationnelles",
    "pratiques operationnelles",
}
REFERENCE_HINTS = {"ce lot", "celui-ci", "celui ci", "ces risques", "ce risque", "cette étape", "cette etape"}
FOLLOWUP_REFERENCE_PATTERN = re.compile(
    r"^(?:et\s+)?(?:celui-ci|celui ci|ce lot|ceux-ci|et celui-ci|et celui ci|et pour\s+(?:la|le|les|l')?)\b",
    re.IGNORECASE,
)
RANKING_FOLLOWUP_PATTERN = re.compile(
    r"\b(?:les?\s+\d+\s+premier\w*|top\s*\d*|premier\w*|suivant\w*|encore)\b",
    re.IGNORECASE,
)
PROCESS_FOLLOWUP_PATTERN = re.compile(
    r"\b(?:celle\s+d['’ ]apres|celle\s+d['’ ]après|d['’ ]apres|d['’ ]après|apres|après|suivante?|etape suivante|étape suivante|et ensuite)\b",
    re.IGNORECASE,
)
INPUTS_FOLLOWUP_PATTERN = re.compile(
    r"\b(?:collect\w*|livr\w*|quantit[eé]\s+re[cç]ue|recu|reçue|aujourd['’]hui|total collect[eé])\b",
    re.IGNORECASE,
)
DATE_RANGE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
LOT_PATTERN = re.compile(r"\b(?:LOT|BATCH|MANG|MANGO|ARA|ARACH|MIL|BISS)[-_][A-Z0-9][A-Z0-9\-_]*\b", re.IGNORECASE)


class IntentRouter:
    """Ruflo-inspired architecture with lightweight agent orchestration and controlled tool execution."""

    def __init__(self, entity_extractor: EntityExtractor | None = None):
        self.entity_extractor = entity_extractor or EntityExtractor()
        self.module_registry = ModuleRegistry()

    def classify(
        self,
        query: str,
        *,
        language_hint: str | None = None,
        known_batch_refs: set[str] | None = None,
        previous_user_query: str | None = None,
    ) -> IntentRouteDecision:
        raw = str(query or "").strip()
        normalized = _normalize(raw)
        lowered = normalized.lower()
        previous_module_hint = self._infer_previous_module_hint(previous_user_query, known_batch_refs=known_batch_refs)

        entities = self.entity_extractor.extract(raw, language_hint=language_hint, known_batch_refs=known_batch_refs).as_dict()
        scope = str(entities.get("scope") or "global")
        module = str(entities.get("module") or "global")
        registry_module = self.module_registry.detect_module(lowered)
        if module in {"global", "rag_knowledge"} and registry_module:
            module = registry_module
            entities["module"] = module
        entities["registry_module"] = registry_module
        entities["module_supported"] = module in self.module_registry.module_keys if module else False
        if previous_module_hint:
            entities["previous_module_hint"] = previous_module_hint

        manager_operational_synthesis = (
            any(token in lowered for token in ("manager", "réponse manager", "reponse manager", "mode manager", "synthèse opérationnelle", "synthese operationnelle", "décision opérationnelle", "decision operationnelle"))
            and any(token in lowered for token in ("conclusion", "conclus", "preuve", "preuves", "action", "actions", "plan d'action", "plan d action", "limite", "limitation", "limites"))
        )
        if manager_operational_synthesis:
            entities["intent_family"] = "action_recommendation"
            return _decision(
                AgentRoute.HYBRID_FULL,
                entities,
                ["SQLAnalyticsAgent", "MLLossAgent", "RAGKnowledgeAgent", "RecommendationAgent"],
                "Manager-style operational synthesis request.",
                0.9,
            )

        if all(
            any(variant in lowered for variant in variants)
            for variants in (
                ("conclusion",),
                ("preuve", "preuves"),
                ("action", "actions"),
                ("limite", "limitation", "limites"),
            )
        ) and any(
            token in lowered for token in ("manager", "lot", "perte", "ml", "rag", "recommand")
        ):
            entities["intent_family"] = "action_recommendation"
            return _decision(
                AgentRoute.HYBRID_FULL,
                entities,
                ["SQLAnalyticsAgent", "MLLossAgent", "RAGKnowledgeAgent", "RecommendationAgent"],
                "Manager-style operational synthesis request.",
                0.9,
            )

        if any(token in lowered for token in ("justificatif", "upload", "fichier", "fichiers")) and any(
            token in lowered for token in ("répartition", "repartition", "par type", "type d'entité", "type d’entité", "entity type")
        ):
            entities["module"] = "collections"
            entities["intent_family"] = "factual_sql"
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Uploaded evidence distribution should be resolved from SQL traceability tables.",
                0.9,
            )
        if any(token in lowered for token in ("perd-on", "perd on", "plus de pertes", "pire perte")) and any(
            token in lowered for token in ("pratiques", "bonnes pratiques", "appliquer", "réduire", "reduire")
        ):
            entities["intent_family"] = "hybrid_analysis"
            return _decision(
                AgentRoute.HYBRID_SQL_RAG,
                entities,
                ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                "Loss-priority + practices request should combine SQL and RAG.",
                0.88,
            )
        independent_guidance_query = any(
            token in lowered
            for token in (
                "humidit",
                "stockage",
                "check-list",
                "checklist",
                "bonnes pratiques",
                "meilleures pratiques",
                "comment eviter",
                "comment éviter",
                "recommand",
            )
        )

        # Follow-up disambiguation from previous module context.
        if (
            previous_module_hint == "members"
            and RANKING_FOLLOWUP_PATTERN.search(lowered)
            and not any(token in lowered for token in ("ml", "anomaly_score", "anomal", "risque", "risk"))
        ):
            entities["module"] = "members"
            entities["intent_family"] = "followup_members_ranking"
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Ranking follow-up tied to previous members context.",
                0.9,
            )
        if (
            previous_module_hint in {"process_steps", "post_harvest", "material_balance"}
            and PROCESS_FOLLOWUP_PATTERN.search(lowered)
            and not independent_guidance_query
        ):
            entities["module"] = "post_harvest"
            entities["scope"] = "post_harvest"
            entities["intent_family"] = "followup_process_step"
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Process-step follow-up tied to previous operational context.",
                0.88,
            )
        if previous_module_hint in {"inputs", "collections"} and INPUTS_FOLLOWUP_PATTERN.search(lowered):
            entities["module"] = "collections"
            entities["scope"] = "global"
            entities["intent_family"] = "followup_inputs_collections"
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Collection follow-up tied to previous inputs context.",
                0.89,
            )
        if RANKING_FOLLOWUP_PATTERN.search(lowered) and any(token in lowered for token in ("pourquoi", "critique", "cause", "explique")):
            entities["module"] = "post_harvest"
            entities["scope"] = "post_harvest"
            entities["intent_family"] = "followup_ranked_item_reasoning"
            if any(token in lowered for token in ("recommand", "action", "ml", "anomaly", "risque")):
                return _decision(
                    AgentRoute.HYBRID_FULL,
                    entities,
                    ["SQLAnalyticsAgent", "MLLossAgent", "RAGKnowledgeAgent", "RecommendationAgent"],
                    "Ranked-item follow-up asks action/recommendation and should include full evidence layers.",
                    0.89,
                )
            return _decision(
                AgentRoute.HYBRID_SQL_RAG,
                entities,
                ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                "Reasoning follow-up on previously ranked operational items.",
                0.86,
            )
        if previous_module_hint in {"post_harvest", "process_steps", "material_balance"} and (
            RANKING_FOLLOWUP_PATTERN.search(lowered) or "critique" in lowered
        ):
            entities["module"] = "post_harvest"
            entities["scope"] = "post_harvest"
            entities["intent_family"] = "followup_postharvest_reasoning"
            if any(token in lowered for token in ("recommand", "action", "ml", "anomaly", "risque")):
                return _decision(
                    AgentRoute.HYBRID_FULL,
                    entities,
                    ["SQLAnalyticsAgent", "MLLossAgent", "RAGKnowledgeAgent", "RecommendationAgent"],
                    "Post-harvest follow-up asks action/recommendation and should include full evidence layers.",
                    0.89,
                )
            if any(token in lowered for token in ("pourquoi", "explique", "why", "cause", "critique")):
                return _decision(
                    AgentRoute.HYBRID_SQL_RAG,
                    entities,
                    ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                    "Post-harvest follow-up explanation tied to previous lot ranking context.",
                    0.89,
                )
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Post-harvest follow-up tied to previous lot ranking context.",
                0.87,
            )

        if self.module_registry.is_capability_question(lowered):
            entities["intent_family"] = "capability"
            return IntentRouteDecision(
                route=AgentRoute.SMALL_TALK,
                confidence=0.97,
                detected_entities=entities,
                required_agents=["SmallTalkAgent"],
                explanation="Capability/help intent detected.",
            )

        if self.module_registry.is_small_talk(lowered) or lowered in SMALL_TALK or len(lowered.split()) <= 2 and lowered in SMALL_TALK:
            entities["intent_family"] = "greeting"
            return IntentRouteDecision(
                route=AgentRoute.SMALL_TALK,
                confidence=0.98,
                detected_entities=entities,
                required_agents=["SmallTalkAgent"],
                explanation="Greeting/small-talk pattern detected.",
            )

        if any(token in lowered for token in OUT_SCOPE) or self.module_registry.is_non_operational_topic(lowered):
            operational_guard = any(
                token in lowered
                for token in (
                    "lot",
                    "lots",
                    "perte",
                    "pertes",
                    "stock",
                    "ml",
                    "anomaly",
                    "anomal",
                    "recommand",
                    "séchage",
                    "sechage",
                    "tri",
                    "conditionnement",
                    "emballage",
                    "post-récolte",
                    "post recolte",
                )
            )
            if operational_guard:
                pass
            else:
                entities["intent_family"] = "unsupported"
                return IntentRouteDecision(
                    route=AgentRoute.OUT_OF_SCOPE,
                    confidence=0.97,
                    detected_entities=entities,
                    required_agents=["OutOfScopeAgent"],
                    explanation="Query appears outside cooperative decision-support domain.",
                )
        if any(token in lowered for token in UNSUPPORTED_FORECAST_HINTS):
            entities["intent_family"] = "unsupported_forecast"
            return IntentRouteDecision(
                route=AgentRoute.OUT_OF_SCOPE,
                confidence=0.96,
                detected_entities=entities,
                required_agents=["OutOfScopeAgent"],
                explanation="Forecasting/external-real-world request outside reliable app-data scope.",
            )
        if any(token in lowered for token in UNSUPPORTED_HR_SUBJECTIVE_HINTS):
            entities["intent_family"] = "unsupported_hr_subjective"
            return IntentRouteDecision(
                route=AgentRoute.OUT_OF_SCOPE,
                confidence=0.97,
                detected_entities=entities,
                required_agents=["OutOfScopeAgent"],
                explanation="Subjective HR/disciplinary decision request outside objective app-data support scope.",
            )
        if "anomaly_score" in lowered and any(token in lowered for token in ("ml", "lot", "batch", "top", "max")):
            entities["intent_family"] = "risk_ml"
            return _decision(
                AgentRoute.HYBRID_SQL_ML,
                entities,
                ["SQLAnalyticsAgent", "MLLossAgent"],
                "Explicit anomaly_score request.",
                0.93,
            )

        asks_recommendation = _has_any(lowered, RECO_HINTS) or any(regex.search(lowered) for regex in RECOMMENDATION_REGEXES)
        asks_explicit_multi_evidence = all(token in lowered for token in ("sql", "ml", "rag")) and any(
            token in lowered for token in ("preuve", "preuves", "avec preuve", "avec les preuves")
        )
        asks_action = any(token in lowered for token in (" action", " actions", "action ", "actions "))
        if not asks_recommendation and asks_action and any(
            token in lowered for token in ("donne", "priorit", "faire", "amélior", "amelior", "réduire", "reduire", "situation")
        ):
            asks_recommendation = True
        if not asks_recommendation and "plan" in lowered and any(token in lowered for token in ("perte", "pertes", "loss", "risque", "risk")):
            asks_recommendation = True
        asks_risk = _has_any(lowered, RISK_HINTS)
        asks_ml_signal = any(
            token in lowered
            for token in (
                "anomaly_score",
                "logs ml",
                "signaux ml",
                "signal ml",
                "classes high",
                "classés high",
                "anormal",
                "alertes ml",
                "alerte ml",
                "high",
            )
        ) and ("ml" in lowered or "anomaly_score" in lowered)
        asks_explanation = _has_any(lowered, EXPLANATION_HINTS)
        if "pk " in lowered or lowered.startswith("pk"):
            asks_explanation = True
        asks_loss = any(token in lowered for token in ("perte", "pertes", "loss", "rendement", "efficacité", "efficacite"))
        asks_anomaly_operational = (
            any(token in lowered for token in ("anomaly", "anomalie", "anomaly_score", "anomal", "risque ml", "signal ml", "modele ml", "modèle ml"))
            and any(token in lowered for token in ("ml", "anomaly", "anomal", "risque"))
            and (
                any(token in lowered for token in ("lot", "lots", "batch", "produit", "etape", "étape"))
                or any(token in lowered for token in ("faits opérationnels", "faits operationnels", "faits oper", "données sql", "donnees sql", "donnees operationnelles", "données opérationnelles", "operational facts"))
            )
        )
        asks_sql_ml_explicit = "sql" in lowered and "ml" in lowered
        asks_sql_ml_rag_explicit = asks_sql_ml_explicit and "rag" in lowered
        asks_manager_full = any(token in lowered for token in ("réponse complète", "reponse complete", "manager", "décision", "decision"))
        asks_reference = any(token in lowered for token in ("référence", "references", "source fiable", "avec source"))
        has_reference_pronoun = _has_any(lowered, REFERENCE_HINTS)
        is_referential_followup = has_reference_pronoun or bool(FOLLOWUP_REFERENCE_PATTERN.search(lowered))
        has_batch_or_postharvest = bool(entities.get("batch_ref")) or scope in {"batch", "post_harvest"}
        asks_collection_sql = bool(INPUTS_FOLLOWUP_PATTERN.search(lowered))

        is_members = module == "members"
        is_member_value = module == "member_value"
        is_collections = module == "collections"
        is_stocks = module == "stocks"
        is_invoices = module == "invoices"
        is_commercial = module == "commercial"
        is_finance = module == "finance"
        is_preharvest = module == "pre_harvest" or scope == "pre_harvest"
        is_material_balance = module == "material_balance" or "bilan matière" in lowered or "bilan matiere" in lowered or "material balance" in lowered
        is_process = has_batch_or_postharvest or any(
            token in lowered
            for token in ("étape", "etape", "process", "flux matière", "flux matiere", "séchage", "sechage", "tri", "emballage", "perte", "loss")
        )
        is_pure_knowledge = module == "rag_knowledge" and not any(
            [is_members, is_member_value, is_collections, is_stocks, is_invoices, is_commercial, is_finance, is_preharvest, is_material_balance, is_process, asks_risk]
        )
        asks_best_practice = _has_any(lowered, BEST_PRACTICE_HINTS)
        asks_procedure_or_precautions = any(
            token in lowered
            for token in (
                "procédure",
                "procedure",
                "précaution",
                "precaution",
                "avant l'emballage",
                "avant emballage",
                "avant de conditionner",
                "conditionner",
                "que faut-il vérifier",
                "que faut il vérifier",
                "que faut-il verifier",
                "que faut il verifier",
                "comment éviter",
                "comment eviter",
                "éviter",
                "eviter",
                "réduire",
                "reduire",
                "conseil",
                "conseils",
            )
        )
        asks_advice_topic = any(
            token in lowered
            for token in ("tri", "séchage", "sechage", "stockage", "humidit", "conditionnement", "conditionner", "casse", "emballage")
        )
        asks_best_practice = asks_best_practice or (asks_procedure_or_precautions and asks_advice_topic)
        asks_practical_guidance = asks_best_practice and any(
            token in lowered for token in ("humidit", "sechage", "séchage", "tri", "stockage", "casse", "check-list", "checklist")
        )
        asks_current_data_scope = any(
            token in lowered
            for token in (
                "dans nos données",
                "dans nos donnees",
                "selon nos données",
                "selon nos donnees",
                "actuel",
                "actuelle",
                "ce lot",
                "ce produit",
                "notre coop",
                "nos lots",
            )
        )
        asks_stock = bool(re.search(r"\bstock(s)?\b", lowered)) or any(token in lowered for token in ("kg", "disponible"))
        asks_compare_product = any(token in lowered for token in ("compare", "compar", "versus", "vs")) and bool(entities.get("product"))
        explicit_operational_target = bool(
            re.search(
                r"\b(lot|lots|batch|stock|collecte|membre|facture|commande|charge|tresorerie|tr[eé]sorerie|coop[eé]rative|production|bl|justificatif|devis|receipt_reference|enregistre_complet|uploaded\s+file|fichier|fichiers|upload|traceabilit[eé])\b",
                lowered,
            )
        )
        asks_loss_best_practice = asks_loss and (asks_best_practice or asks_explanation) and (
            has_batch_or_postharvest or bool(entities.get("stage")) or bool(entities.get("product"))
        )
        asks_multi_sql_rag = asks_stock and (asks_best_practice or asks_explanation or asks_reference)
        asks_sql_plus_rag = "sql" in lowered and (asks_best_practice or asks_explanation or asks_reference)
        asks_operational_advice_combo = (
            (
                explicit_operational_target
                or asks_current_data_scope
                or (
                    asks_loss
                    and (
                        has_batch_or_postharvest
                        or bool(entities.get("stage"))
                        or bool(entities.get("product"))
                        or explicit_operational_target
                        or asks_current_data_scope
                    )
                )
            )
            and (
                asks_best_practice
                or asks_explanation
                or any(
                    token in lowered
                    for token in ("que faire", "comment améliorer", "comment ameliorer", "conseils", "comment corriger", "corriger", "corrige")
                )
            )
            and not asks_risk
            and not asks_ml_signal
            and not asks_recommendation
        )
        asks_data_plus_rag_action = (
            asks_action
            and asks_loss
            and (asks_best_practice or "rag" in lowered or "base rag" in lowered)
            and any(token in lowered for token in ("nos données", "nos donnees", "selon nos données", "selon nos donnees"))
        )

        if (
            asks_best_practice
            and not explicit_operational_target
            and not asks_current_data_scope
            and not entities.get("batch_ref")
            and "sql" not in lowered
            and "nos données" not in lowered
            and "nos donnees" not in lowered
            and not asks_risk
            and not asks_ml_signal
        ):
            entities["intent_family"] = "explanation"
            return _decision(
                AgentRoute.RAG_ONLY,
                entities,
                ["RAGKnowledgeAgent"],
                "Pure best-practice guidance without explicit app-data scope should stay in RAG mode.",
                0.9,
            )

        if asks_sql_ml_rag_explicit or (asks_manager_full and asks_sql_ml_explicit and asks_recommendation):
            entities["intent_family"] = "action_recommendation"
            return _decision(
                AgentRoute.HYBRID_FULL,
                entities,
                ["SQLAnalyticsAgent", "MLLossAgent", "RAGKnowledgeAgent", "RecommendationAgent"],
                "Explicit full-stack SQL+ML+RAG+recommendation request.",
                0.92,
            )
        if asks_manager_full and asks_recommendation and (
            explicit_operational_target or asks_loss or asks_risk or asks_ml_signal or asks_current_data_scope
        ):
            entities["intent_family"] = "action_recommendation"
            return _decision(
                AgentRoute.HYBRID_FULL,
                entities,
                ["SQLAnalyticsAgent", "MLLossAgent", "RAGKnowledgeAgent", "RecommendationAgent"],
                "Manager-style operational recommendation synthesis.",
                0.9,
            )

        if asks_sql_ml_explicit and not asks_recommendation:
            entities["intent_family"] = "risk_ml"
            return _decision(
                AgentRoute.HYBRID_SQL_ML,
                entities,
                ["SQLAnalyticsAgent", "MLLossAgent"],
                "Explicit SQL+ML comparison request.",
                0.9,
            )

        if asks_sql_ml_explicit and asks_recommendation:
            entities["intent_family"] = "action_recommendation"
            return _decision(
                AgentRoute.HYBRID_FULL,
                entities,
                ["SQLAnalyticsAgent", "MLLossAgent", "RAGKnowledgeAgent", "RecommendationAgent"],
                "SQL+ML request that also asks recommendation/action must use full hybrid route.",
                0.91,
            )

        if asks_anomaly_operational:
            entities["intent_family"] = "risk_ml"
            return _decision(
                AgentRoute.HYBRID_SQL_ML,
                entities,
                ["SQLAnalyticsAgent", "MLLossAgent"],
                "Anomaly + operational facts request should combine SQL and ML.",
                0.9,
            )

        if asks_data_plus_rag_action:
            entities["intent_family"] = "action_recommendation"
            return _decision(
                AgentRoute.HYBRID_FULL,
                entities,
                ["SQLAnalyticsAgent", "MLLossAgent", "RAGKnowledgeAgent", "RecommendationAgent"],
                "Operational data + RAG action request should include recommendation and ML layers.",
                0.9,
            )

        if asks_operational_advice_combo:
            entities["intent_family"] = "hybrid_analysis"
            return _decision(
                AgentRoute.HYBRID_SQL_RAG,
                entities,
                ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                "Operational data + advice request should combine SQL and RAG.",
                0.88,
            )

        if asks_loss and (asks_best_practice or asks_recommendation or asks_explanation) and not asks_ml_signal:
            entities["intent_family"] = "hybrid_analysis"
            return _decision(
                AgentRoute.HYBRID_SQL_RAG,
                entities,
                ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                "Loss-focused improvement/action request should combine SQL and RAG.",
                0.87,
            )

        if asks_current_data_scope and ("perd" in lowered or asks_loss or "loss" in lowered) and (asks_best_practice or asks_explanation or asks_recommendation):
            entities["intent_family"] = "hybrid_analysis"
            return _decision(
                AgentRoute.HYBRID_SQL_RAG,
                entities,
                ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                "Current cooperative loss diagnostics + improvement request should combine SQL and RAG.",
                0.9,
            )

        if asks_practical_guidance and not asks_loss and not entities.get("batch_ref") and not asks_risk and not asks_ml_signal and not explicit_operational_target and not asks_current_data_scope:
            entities["intent_family"] = "explanation"
            return _decision(
                AgentRoute.RAG_ONLY,
                entities,
                ["RAGKnowledgeAgent"],
                "Practical best-practice guidance should prioritize RAG knowledge.",
                0.9,
            )

        if asks_multi_sql_rag:
            entities["intent_family"] = "multi_intent"
            return _decision(
                AgentRoute.HYBRID_SQL_RAG,
                entities,
                ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                "Question multi-intention SQL + bonnes pratiques.",
                0.9,
            )

        if asks_sql_plus_rag:
            entities["intent_family"] = "multi_intent"
            return _decision(
                AgentRoute.HYBRID_SQL_RAG,
                entities,
                ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                "Explicit SQL + best-practice request.",
                0.9,
            )

        if asks_compare_product and not asks_risk and not asks_ml_signal and not asks_recommendation:
            entities["intent_family"] = "factual_sql"
            entities["module"] = "stocks"
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Product comparison follow-up mapped to stock SQL module.",
                0.83,
            )

        if asks_loss_best_practice:
            entities["intent_family"] = "hybrid_analysis"
            return _decision(
                AgentRoute.HYBRID_SQL_RAG,
                entities,
                ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                "Loss + best-practice question requires SQL facts and RAG explanation.",
                0.88,
            )

        if asks_best_practice and not asks_risk and not asks_ml_signal and not asks_recommendation:
            entities["intent_family"] = "explanation"
            if asks_current_data_scope or entities.get("batch_ref") or asks_loss or "sql" in lowered:
                return _decision(
                    AgentRoute.HYBRID_SQL_RAG,
                    entities,
                    ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                    "Best-practice question with explicit operational scope should combine SQL and RAG.",
                    0.87,
                )
            return _decision(
                AgentRoute.RAG_ONLY,
                entities,
                ["RAGKnowledgeAgent"],
                "Pure best-practice/procedure guidance should prioritize RAG knowledge.",
                0.9,
            )

        if asks_best_practice and (is_process or bool(entities.get("product")) or bool(entities.get("stage"))) and (
            explicit_operational_target or asks_current_data_scope or has_batch_or_postharvest
        ):
            entities["intent_family"] = "explanation"
            return _decision(
                AgentRoute.HYBRID_SQL_RAG,
                entities,
                ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                "Best-practice question with operational context should combine SQL and RAG.",
                0.84,
            )

        if asks_best_practice and asks_recommendation and not explicit_operational_target and not asks_current_data_scope and not asks_loss and not asks_risk and not asks_ml_signal:
            entities["intent_family"] = "explanation"
            return _decision(
                AgentRoute.RAG_ONLY,
                entities,
                ["RAGKnowledgeAgent"],
                "Pure best-practice advice wording should stay in RAG mode.",
                0.86,
            )

        if asks_explicit_multi_evidence:
            entities["intent_family"] = "action_recommendation"
            return _decision(
                AgentRoute.HYBRID_FULL,
                entities,
                ["SQLAnalyticsAgent", "MLLossAgent", "RAGKnowledgeAgent", "RecommendationAgent"],
                "Explicit multi-evidence recommendation request (SQL+ML+RAG).",
                0.9,
            )

        if asks_recommendation:
            entities["intent_family"] = "action_recommendation"
            if (
                is_members
                or is_collections
                or is_stocks
                or is_preharvest
                or is_process
                or is_material_balance
                or asks_risk
                or asks_loss
                or has_reference_pronoun
                or explicit_operational_target
            ):
                return _decision(
                    AgentRoute.HYBRID_FULL,
                    entities,
                    ["SQLAnalyticsAgent", "MLLossAgent", "RAGKnowledgeAgent", "RecommendationAgent"],
                    "Recommendation with operational context.",
                    0.86,
                )
            if asks_explanation or is_pure_knowledge:
                return _decision(
                    AgentRoute.HYBRID_RAG_RECOMMENDATION,
                    entities,
                    ["RAGKnowledgeAgent", "RecommendationAgent"],
                    "Knowledge-backed recommendation request.",
                    0.84,
                )
            return _decision(
                AgentRoute.RECOMMENDATION_ONLY,
                entities,
                ["RecommendationAgent"],
                "Recommendation-only request.",
                0.76,
            )

        if asks_risk or asks_ml_signal:
            entities["intent_family"] = "risk_ml"
            return _decision(
                AgentRoute.HYBRID_SQL_ML,
                entities,
                ["SQLAnalyticsAgent", "MLLossAgent"],
                "Risk or anomaly operational request.",
                0.9,
            )

        if is_collections or asks_collection_sql:
            entities["intent_family"] = "factual_sql"
            entities["module"] = "collections"
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Collection/input quantity request.",
                0.9,
            )

        if is_members or is_member_value or is_collections or is_invoices or is_commercial or is_finance:
            entities["intent_family"] = "factual_sql"
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Operational business data request.",
                0.9,
            )

        if is_stocks:
            entities["intent_family"] = "factual_sql"
            if asks_explanation or asks_best_practice or asks_reference or asks_loss:
                return _decision(
                    AgentRoute.HYBRID_SQL_RAG,
                    entities,
                    ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                    "Stock question with explicit explanation or best-practice request.",
                    0.84,
                )
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Operational stock request.",
                0.9,
            )

        if is_preharvest:
            entities["intent_family"] = "factual_sql"
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Pre-harvest operational request.",
                0.88,
            )

        if is_material_balance:
            entities["intent_family"] = "hybrid_analysis" if (asks_explanation or asks_best_practice) else "factual_sql"
            if asks_explanation or asks_best_practice:
                return _decision(
                    AgentRoute.HYBRID_SQL_RAG,
                    entities,
                    ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                    "Material balance with explicit explanation.",
                    0.84,
                )
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Material balance operational request.",
                0.88,
            )

        if asks_best_practice and not explicit_operational_target and not asks_loss and not is_process and not entities.get("product") and not entities.get("stage"):
            entities["intent_family"] = "explanation"
            return _decision(
                AgentRoute.RAG_ONLY,
                entities,
                ["RAGKnowledgeAgent"],
                "Best-practice question should prioritize knowledge retrieval.",
                0.86,
            )

        if asks_reference and not explicit_operational_target and not is_process:
            entities["intent_family"] = "explanation"
            return _decision(
                AgentRoute.RAG_ONLY,
                entities,
                ["RAGKnowledgeAgent"],
                "Reference-seeking question should prioritize knowledge retrieval.",
                0.84,
            )

        if is_process:
            entities["intent_family"] = "hybrid_analysis" if asks_explanation else "factual_sql"
            if asks_explanation:
                return _decision(
                    AgentRoute.HYBRID_SQL_RAG,
                    entities,
                    ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                    "Process/loss request with explanation.",
                    0.85,
                )
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Process/loss operational request.",
                0.89,
            )

        if is_referential_followup:
            entities["intent_family"] = "followup_reference"
            if asks_recommendation:
                return _decision(
                    AgentRoute.HYBRID_FULL,
                    entities,
                    ["SQLAnalyticsAgent", "MLLossAgent", "RAGKnowledgeAgent", "RecommendationAgent"],
                    "Referential follow-up with action request.",
                    0.84,
                )
            if asks_explanation or asks_loss or asks_best_practice:
                return _decision(
                    AgentRoute.HYBRID_SQL_RAG,
                    entities,
                    ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                    "Referential follow-up requiring SQL + explanation.",
                    0.83,
                )
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Referential follow-up mapped to prior operational context.",
                0.82,
            )

        if is_pure_knowledge or asks_explanation or asks_reference:
            entities["intent_family"] = "explanation"
            return _decision(
                AgentRoute.RAG_ONLY,
                entities,
                ["RAGKnowledgeAgent"],
                "Knowledge or best-practice explanation request.",
                0.82,
            )

        if not self.module_registry.is_operational_topic(lowered, module_hint=module):
            entities["intent_family"] = "unsupported"
            return _decision(
                AgentRoute.OUT_OF_SCOPE,
                entities,
                ["OutOfScopeAgent"],
                "No supported operational module target detected.",
                0.83,
            )

        entities["intent_family"] = "factual_sql"
        return _decision(
            AgentRoute.SQL_ONLY,
            entities,
            ["SQLAnalyticsAgent"],
            "Default deterministic operational fallback.",
            0.7,
        )

    def _infer_previous_module_hint(self, previous_user_query: str | None, *, known_batch_refs: set[str] | None = None) -> str | None:
        text = str(previous_user_query or "").strip()
        if not text:
            return None
        extracted = self.entity_extractor.extract(text, known_batch_refs=known_batch_refs).as_dict()
        module = str(extracted.get("module") or "").strip().lower()
        scope = str(extracted.get("scope") or "").strip().lower()
        lowered = _normalize(text).lower()
        if module in {"members", "member_value"}:
            return "members"
        if module in {"collections"}:
            return "inputs"
        if module in {"material_balance"}:
            return "material_balance"
        if module in {"post_harvest"}:
            if any(token in lowered for token in ("étape", "etape", "process", "séchage", "sechage", "tri", "emballage")):
                return "process_steps"
            return "post_harvest"
        if scope in {"batch", "post_harvest"} and any(token in lowered for token in ("étape", "etape", "process", "séchage", "sechage", "tri", "emballage")):
            return "process_steps"
        if any(token in lowered for token in ("collecte", "collectée", "collectee", "livré", "livre", "quantité", "quantite", "input")):
            return "inputs"
        if any(token in lowered for token in ("membre", "membres", "top", "classement", "plus livré", "plus livre")):
            return "members"
        return None


def _decision(route: AgentRoute, entities: dict, agents: list[str], explanation: str, confidence: float) -> IntentRouteDecision:
    return IntentRouteDecision(
        route=route,
        confidence=confidence,
        detected_entities=entities,
        required_agents=agents,
        explanation=explanation,
    )


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _detect_products(text: str) -> list[str]:
    return sorted({canonical for token, canonical in PRODUCT_MAP.items() if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text)})


def _detect_stages(text: str) -> list[str]:
    return sorted({canonical for token, canonical in STAGE_MAP.items() if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text)})


def _detect_lot(text: str) -> str | None:
    match = LOT_PATTERN.search(text or "")
    return match.group(0).upper() if match else None


def _detect_member(text: str) -> str | None:
    match = re.search(r"(?:membre|member|farmer)\s+([A-Za-z][\w\- ]{1,60})", text or "", re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def _detect_metrics(text: str) -> list[str]:
    metric_map = {
        "perte": "loss",
        "loss": "loss",
        "efficacite": "efficiency",
        "efficacité": "efficiency",
        "efficiency": "efficiency",
        "stock": "stock",
        "collecte": "collection",
        "anomal": "anomaly",
        "risque": "risk",
        "risk": "risk",
        "recommand": "recommendation",
    }
    result = {value for key, value in metric_map.items() if key in text}
    return sorted(result)


def _detect_language(text: str, hint: str | None) -> str:
    if hint:
        hinted = str(hint).lower().strip()
        if hinted in {"fr", "en", "ar"}:
            return hinted
    french_markers = {"bonjour", "quel", "pourquoi", "lot", "séchage", "efficacité"}
    english_markers = {"hello", "what", "why", "which", "batch", "drying"}
    fr_hits = sum(1 for token in french_markers if token in text)
    en_hits = sum(1 for token in english_markers if token in text)
    if en_hits > fr_hits:
        return "en"
    return "fr"


def _has_any(text: str, hints: set[str]) -> bool:
    return any(hint in text for hint in hints)


def _is_stage_loss_causal_question(text: str, entities: dict) -> bool:
    if not entities.get("stage") or "loss" not in (entities.get("metric") or []):
        return False
    causal_terms = ("pourquoi", "why", "cause", "causes", "élev", "eleve", "beaucoup", "forte", "fortes")
    return any(term in text for term in causal_terms)
