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
UI_ACTION_HINTS = {
    "connecte-toi",
    "connecte toi",
    "connecte toi avec",
    "login",
    "log in",
    "verifie le dashboard",
    "vérifie le dashboard",
    "ouvre la page",
    "ouvrir la page",
    "teste la page",
    "tester la page",
    "dashboard charge",
    "dashboard load",
    "vérifie l’interface",
    "verifie l'interface",
    "verifie l’interface",
    "va dans la page",
    "page stocks",
}
UNSAFE_OPERATION_HINTS = {
    "supprime",
    "supprimer",
    "delete",
    "invente",
    "falsifie",
    "manipule",
    "manipuler",
    "sans confirmation",
    "without confirmation",
}
UNSUPPORTED_FORECAST_HINTS = {
    "predis",
    "prédis",
    "predire",
    "prédire",
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
    "quelle action",
    "quelles actions",
    "actions confirmees",
    "actions confirmées",
    "recommandations prouvees",
    "recommandations prouvées",
    "recommandation prouvee",
    "recommandation prouvée",
    "sans te baser uniquement sur ml",
    "sans se baser uniquement sur ml",
    "reco",
    "action fiable",
    "actions fiables",
    "que recommandes-tu",
    "que recommandes tu",
    "recommandation",
    "recommandations",
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
    "gestes simples",
    "mieux stocker",
    "avant transformation",
    "avant stockage",
    "eviter la casse",
    "éviter la casse",
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
    "gestes simples",
    "mieux stocker",
    "avant transformation",
    "avant stockage",
    "eviter la casse",
    "éviter la casse",
    "comment organiser le nettoyage",
    "quels contrôles minimum",
    "quels controles minimum",
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
        previous_module_hint = _infer_previous_module_hint(previous_user_query, self.entity_extractor, known_batch_refs=known_batch_refs)

        entities = self.entity_extractor.extract(raw, language_hint=language_hint, known_batch_refs=known_batch_refs).as_dict()
        explicit_product_focus = re.search(r"\bproduit\s+([^,:;]+)", raw, re.IGNORECASE)
        if explicit_product_focus and not entities.get("product"):
            label = explicit_product_focus.group(1).strip()
            if label:
                entities["product"] = [label]
        explicit_lot_focus = re.search(r"\banalyse\s+([A-Z0-9][A-Z0-9\-_]+)\s+uniquement\b", raw, re.IGNORECASE)
        if explicit_lot_focus:
            entities["batch_ref"] = explicit_lot_focus.group(1).upper()
        previous_entities = self.entity_extractor.extract(previous_user_query or "", known_batch_refs=known_batch_refs).as_dict() if previous_user_query else {}
        referential_tokens = ("le premier", "ce lot", "ce produit", "cette étape", "cette etape", "celui-ci", "celui ci")
        if any(token in lowered for token in referential_tokens):
            if not entities.get("batch_ref") and previous_entities.get("batch_ref"):
                entities["batch_ref"] = previous_entities.get("batch_ref")
            if not entities.get("product") and previous_entities.get("product"):
                entities["product"] = previous_entities.get("product")
            if not entities.get("stage") and previous_entities.get("stage"):
                entities["stage"] = previous_entities.get("stage")
            if (not entities.get("module") or entities.get("module") == "global") and previous_entities.get("module"):
                entities["module"] = previous_entities.get("module")
            if (not entities.get("scope") or entities.get("scope") == "global") and previous_entities.get("scope"):
                entities["scope"] = previous_entities.get("scope")
        if any(token in lowered for token in UI_ACTION_HINTS):
            entities["intent_family"] = "unsupported_ui_action"
            return _decision(
                AgentRoute.OUT_OF_SCOPE,
                entities,
                ["OutOfScopeAgent"],
                "UI/action command detected; chatbot should provide guidance instead of analytics.",
                0.99,
            )
        has_unsafe_hint = any(token in lowered for token in UNSAFE_OPERATION_HINTS)
        if "sans inventer" in lowered or "without inventing" in lowered:
            has_unsafe_hint = False
        if has_unsafe_hint:
            entities["intent_family"] = "unsupported_unsafe_action"
            return _decision(
                AgentRoute.OUT_OF_SCOPE,
                entities,
                ["OutOfScopeAgent"],
                "Unsafe/manipulative action request detected; refuse analytics/action execution.",
                0.99,
            )
        contract = _contract_route_decision(
            lowered=lowered,
            entities=entities,
            previous_entities=previous_entities,
            previous_module_hint=previous_module_hint,
        )
        if contract is not None:
            return contract
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
        if previous_module_hint and RANKING_FOLLOWUP_PATTERN.search(lowered) and any(token in lowered for token in ("pourquoi", "critique", "cause", "explique")):
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
                    "ecart",
                    "écart",
                    "entree",
                    "entrée",
                    "sortie",
                    "rendement",
                    "matiere",
                    "matière",
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
        unsupported_hr_hit = any(token in lowered for token in UNSUPPORTED_HR_SUBJECTIVE_HINTS)
        lot_reference_validation_reco = (
            unsupported_hr_hit
            and bool(LOT_PATTERN.search(lowered))
            and (
                _has_any(lowered, RECO_HINTS)
                or any(regex.search(lowered) for regex in RECOMMENDATION_REGEXES)
                or "action" in lowered
            )
            and any(token in lowered for token in ("sinon", "invalide", "invalid", "reference", "référence", "introuvable", "action fiable", "actions fiables"))
        )
        if unsupported_hr_hit and not lot_reference_validation_reco:
            entities["intent_family"] = "unsupported_hr_subjective"
            return IntentRouteDecision(
                route=AgentRoute.OUT_OF_SCOPE,
                confidence=0.97,
                detected_entities=entities,
                required_agents=["OutOfScopeAgent"],
                explanation="Subjective HR/disciplinary decision request outside objective app-data support scope.",
            )
        if "stock" in lowered and any(token in lowered for token in ("risque de rupture", "rupture", "seuil critique", "sous le seuil", "proche du seuil")):
            entities["intent_family"] = "factual_sql"
            entities["module"] = "stocks"
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Stock threshold/rupture question should remain SQL low-stock domain.",
                0.93,
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
            token in lowered for token in ("donne", "propose", "proposer", "priorit", "faire", "amélior", "amelior", "réduire", "reduire", "situation", "confirm")
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
        asks_loss = any(token in lowered for token in ("perte", "pertes", "loss", "rendement", "efficacité", "efficacite", "lowest efficiency", "pire efficacité", "pire efficacite"))
        asks_loss = asks_loss or bool(
            re.search(r"\b(ecarts?|écarts?|gap|difference)\b.*\b(entree|entrée|input)\b.*\b(sortie|output)\b", lowered)
            or re.search(r"\b(bilan matiere|bilan matière|material balance)\b.*\b(lot|batch)\b", lowered)
            or re.search(r"\b(loss|efficiency)\s+ranking\b", lowered)
            or re.search(r"\b(rendement le plus faible|plus mauvais rendement|lowest yield)\b", lowered)
        )
        postharvest_loss_ranking_intent = bool(
            (
                re.search(r"\b(lot|lots|batch|batches)\b", lowered)
                or re.search(r"\b(ecarts?|écarts?|gap|difference)\b.*\b(entree|entrée|input)\b.*\b(sortie|output)\b", lowered)
            )
            and (
                re.search(r"\b(top|classement|classe|ranking|critiques?|prioris|pire|pires|plus elev|plus eleve|plus fortes?|plus\s+penalis\w*)\b", lowered)
                or re.search(r"\b(perte|pertes|loss|efficacite|efficacité|efficiency|rendement|matiere|matière)\b", lowered)
                or re.search(r"\b(ecarts?|écarts?|gap|difference)\b.*\b(entree|entrée|input)\b.*\b(sortie|output)\b", lowered)
                or re.search(r"\b(bilan matiere|bilan matière|material balance)\b", lowered)
                or (re.search(r"\bpost-?recolte|post-?harvest\b", lowered) and re.search(r"\b(top|classement|classe|ranking|critiques?|prioris|pire|pires|plus elev|plus eleve|plus fortes?|plus\s+penalis\w*)\b", lowered))
            )
        )
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
                r"\b(lot|lots|batch|stock|collecte|membre|facture|commande|charge|tresorerie|tr[eé]sorerie|coop[eé]rative|production|bl|justificatif|devis|receipt_reference|enregistre_complet|uploaded\s+file|fichier|fichiers|upload|traceabilit[eé]|perte|pertes|loss|s[eé]chage|tri|emballage|conditionnement)\b",
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

        if asks_recommendation and re.search(r"\b(lot|batch)\b", lowered) and not entities.get("batch_ref"):
            entities["intent_family"] = "follow_up"
            entities["needs_batch_clarification"] = True
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Recommendation request mentions lot/batch without explicit reference; clarification required.",
                0.89,
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
        if ("produit" in lowered and ("seulement" in lowered or "uniquement" in lowered) and ("action" in lowered or "recommand" in lowered)):
            entities["intent_family"] = "action_recommendation"
            return _decision(
                AgentRoute.HYBRID_FULL,
                entities,
                ["SQLAnalyticsAgent", "MLLossAgent", "RAGKnowledgeAgent", "RecommendationAgent"],
                "Product-anchored action request should include hybrid evidence layers.",
                0.9,
            )

        if any(token in lowered for token in ("seuil critique", "sous le seuil", "proche du seuil", "risque de rupture")) and "stock" in lowered:
            entities["intent_family"] = "factual_sql"
            entities["module"] = "stocks"
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Stock threshold/rupture wording should route to deterministic SQL stock alerts.",
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

        if any(token in lowered for token in ("mouvement", "mouvements", "stock movement", "journal mouvements")):
            entities["intent_family"] = "factual_sql"
            entities["module"] = "stocks"
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Stock movement request should be deterministic SQL.",
                0.92,
            )

        if postharvest_loss_ranking_intent:
            entities["intent_family"] = "factual_sql"
            entities["module"] = "post_harvest"
            if asks_ml_signal:
                return _decision(
                    AgentRoute.HYBRID_SQL_ML,
                    entities,
                    ["SQLAnalyticsAgent", "MLLossAgent"],
                    "Post-harvest loss ranking with ML signal request.",
                    0.92,
                )
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Post-harvest loss ranking should use deterministic SQL with strict ranking renderer.",
                0.92,
            )

        if ("top" in lowered and "lot" in lowered and "critique" in lowered and not asks_recommendation and not asks_explanation):
            entities["intent_family"] = "factual_sql"
            entities["module"] = "post_harvest"
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Top critical lots without explicit recommendation/explanation should stay SQL-only.",
                0.88,
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

        if asks_loss and (asks_best_practice or asks_explanation) and not asks_ml_signal:
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


def _contract_route_decision(
    *,
    lowered: str,
    entities: dict,
    previous_entities: dict,
    previous_module_hint: str | None,
) -> IntentRouteDecision | None:
    lowered_ascii = "".join(ch for ch in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(ch))
    if "stock" in lowered_ascii and any(token in lowered_ascii for token in ("risque de rupture", "rupture", "seuil critique", "sous le seuil", "proche du seuil")):
        entities["intent_family"] = "factual_sql"
        entities["module"] = "stocks"
        return _decision(
            AgentRoute.SQL_ONLY,
            entities,
            ["SQLAnalyticsAgent"],
            "Contract guard: stock rupture/threshold query should map to SQL low-stock operation.",
            0.94,
        )
    reset_context = any(
        token in lowered
        for token in (
            "oublie ce lot",
            "oublier ce lot",
            "ignore ce lot",
            "ignore ce lot",
            "change de sujet",
            "changeons de sujet",
            "maintenant parle-moi seulement de",
            "maintenant parle moi seulement de",
            "seulement le stock de",
            "on passe au stock de",
        )
    )
    if reset_context:
        entities.pop("batch_ref", None)
        entities.pop("batch_ref_candidate", None)
        entities["specific_batch_requested"] = False
        entities["scope"] = "global"

    has_batch = bool(entities.get("batch_ref"))
    has_lot_mention = bool(re.search(r"\b(lot|lots|batch|batches)\b", lowered_ascii))
    has_operational_anchor = has_batch or bool(entities.get("product")) or bool(entities.get("stage")) or has_lot_mention
    asks_current_scope = any(
        token in lowered_ascii
        for token in (
            "dans nos donnees",
            "selon nos donnees",
            "notre coop",
            "cette cooperative",
            "dans la base",
            "dans nos lots",
            "dans nos stocks",
        )
    )
    asks_recommendation = any(
        token in lowered
        for token in (
            "que faire",
            "que dois-je faire",
            "que dois je faire",
            "quelles actions",
            "quelle action",
            "actions fiables",
            "actions à appliquer",
            "actions a appliquer",
            "actions concretes",
            "actions concrètes",
            "plan d'action",
            "plan d action",
            "on fait quoi",
            "on devrait faire quoi",
            "actions prioritaires",
            "action prioritaire",
            "recommandations disponibles",
            "recommandation disponible",
            "que recommandes",
            "tu recommandes",
            "conseilles quoi",
            "conseille quoi",
            "dois-je faire",
            "dois je faire",
            "quelles mesures",
            "quelle mesure",
            "mesures immediates",
            "mesures immédiates",
            "mesures a lancer",
            "mesures à lancer",
        )
    )
    if "recommand" in lowered and any(token in lowered for token in ("action", "actions", "priorit", "faire", "plan")):
        asks_recommendation = True
    asks_risk = any(token in lowered for token in ("risque", "risk", "anomal", "prediction", "prédiction", "probabil"))
    asks_why = any(token in lowered for token in ("pourquoi", "cause", "explique", "why"))
    asks_best_practice = any(
        token in lowered
        for token in (
            "bonnes pratiques",
            "meilleures pratiques",
            "best practices",
            "erreurs à éviter",
            "erreurs a eviter",
            "faut-il éviter",
            "faut il eviter",
            "checklist",
            "check-list",
            "précautions",
            "precautions",
            "avant l'emballage",
            "avant emballage",
            "procedure",
            "procédure",
            "conseil",
            "conseils",
            "stockage",
            "pratiques de stockage",
            "pratiques de conditionnement",
            "comment améliorer",
            "comment ameliorer",
            "comment réduire",
            "comment reduire",
            "comment limiter",
            "limiter les pertes",
            "comment organiser",
            "liste de vérifications",
            "liste de verifications",
            "pratiques simples",
            "criteres concrets",
            "critères concrets",
            "que controler",
            "que contrôler",
            "quoi verifier",
            "quoi vérifier",
            "points verifier",
            "points vérifier",
            "avant d'emballer",
            "avant d emballer",
            "mise en stock",
            "entreposer",
            "avant transformation",
        )
    )
    stage_guidance_context = any(
        token in lowered_ascii
        for token in (
            "nettoyage",
            "sechage",
            "tri",
            "emballage",
            "emballer",
            "conditionnement",
            "stockage",
            "entreposer",
            "mise en stock",
            "transformation",
            "post-recolte",
            "post recolte",
            "post-harvest",
        )
    )
    advisory_intent = asks_best_practice or any(
        token in lowered_ascii
        for token in (
            "comment organiser",
            "bonnes pratiques",
            "checklist",
            "liste de verifications",
            "pratiques simples",
            "criteres concrets",
            "que controler",
            "quoi verifier",
            "precautions",
            "conseils",
        )
    )
    explicit_operational_metrics = any(
        token in lowered_ascii
        for token in (
            "combien",
            "quantites",
            "quantite",
            "total",
            "actuel",
            "stock actuel",
            "mouvements",
            "pertes mesurees",
            "classement",
            "par lot",
            "par producteur",
            "factures",
            "tresorerie",
        )
    )
    if advisory_intent and stage_guidance_context and not explicit_operational_metrics and not asks_risk and not asks_recommendation:
        entities["intent_family"] = "BEST_PRACTICES"
        return _decision(
            AgentRoute.RAG_ONLY,
            entities,
            ["RAGKnowledgeAgent"],
            "Best-practice stage guidance without operational metric request should route to RAG.",
            0.91,
        )
    asks_measured_analytics = explicit_operational_metrics or any(
        token in lowered_ascii
        for token in (
            "mesure",
            "mesuree",
            "mesuree",
            "mesurées",
            "classement",
            "classe les etapes",
            "classement des etapes",
            "par pertes",
            "par etape",
            "total",
            "dans notre cooperative",
            "dans notre coop",
            "dans nos donnees",
            "selon nos donnees",
        )
    )
    asks_educational_stage_advice = stage_guidance_context and (
        advisory_intent
        or (
            asks_why
            and any(token in lowered_ascii for token in ("sechage", "tri", "stockage", "entreposer", "mise en stock", "emballage", "conditionnement"))
        )
        or any(token in lowered_ascii for token in ("criteres de tri", "critères de tri", "points verifier", "points vérifier", "checklist", "check-list"))
    )
    if (
        asks_educational_stage_advice
        and not asks_recommendation
        and not asks_risk
        and not asks_current_scope
        and not has_batch
        and not asks_measured_analytics
        and not bool(re.search(r"\bstock(?:s)?\b", lowered_ascii))
    ):
        entities["intent_family"] = "BEST_PRACTICES"
        return _decision(
            AgentRoute.RAG_ONLY,
            entities,
            ["RAGKnowledgeAgent"],
            "Educational post-harvest advice request without measured-data scope should route to RAG.",
            0.92,
        )
    asks_loss = any(
        token in lowered
        for token in ("perte", "pertes", "loss", "efficacite", "efficacité", "efficac", "rendement", "penalis", "pénalis", "perdu", "perdus")
    )
    asks_gap = bool(
        re.search(r"\b(ecarts?|écarts?|gap|difference)\b.*\b(entree|entrée|input)\b.*\b(sortie|output)\b", lowered)
        or re.search(r"\b(entree|entrée|input)\b.*\b(sortie|output)\b", lowered)
        or "écart matière" in lowered
        or "ecart matiere" in lowered
        or "différence entrée sortie" in lowered
        or "difference entree sortie" in lowered
        or re.search(r"\b(quantite|quantité)\s+perdu", lowered)
        or re.search(r"\bperdu\s+le\s+plus\s+de\s+(quantite|quantité)\b", lowered)
        or re.search(r"\bplus\s+de\s+(quantite|quantité)\s+perdue?\b", lowered)
        or re.search(r"\bperte\s+en\s+kg\b", lowered)
        or re.search(r"\bperte\s+(matiere|matière)\s+en\s+kilogrammes?\b", lowered)
        or re.search(r"\bperte\s+(matiere|matière)\b.*\b(kilogrammes?|kg)\b", lowered)
        or re.search(r"\becart\s+de\s+matiere\b", lowered)
        or re.search(r"\bécart\s+de\s+matière\b", lowered)
        or re.search(r"\brange\s+les\s+lots\s+selon\s+la\s+quantite\s+perdue\b", lowered)
        or re.search(r"\bclasse\s+les\s+lots\s+par\s+(ecart|écart|difference|différence)\b", lowered)
    )
    asks_gap_by_qty = asks_gap and any(
        token in lowered
        for token in (
            "kg",
            "quantite",
            "quantité",
            "matiere",
            "matière",
            "ecart",
            "écart",
            "difference entree sortie",
            "différence entrée sortie",
        )
    )
    asks_available_lots = any(
        token in lowered
        for token in (
            "lots disponibles",
            "lots post-récolte",
            "lots post recolte",
            "post-harvest lots",
            "postharvest lots",
            "lots enregistres",
            "lots enregistrés",
            "lots prêts pour post-récolte",
            "lots prets pour post-recolte",
            "lots utilisables pour transformation",
            "lots encore utilisables pour lancer une transformation",
            "lots prêts à transformer",
            "lots prets a transformer",
            "lots disponibles à traiter",
            "lots disponibles a traiter",
            "lots prets a traiter",
            "lots prêts à traiter",
            "quantité restante pour transformation",
            "quantite restante pour transformation",
            "lancer une transformation",
            "prêts pour la post-récolte",
            "prets pour la post-recolte",
            "utilisables",
            "transformer",
        )
    )
    asks_available_lots = asks_available_lots or bool(
        re.search(r"\blots?\b.*\b(pret|prêt|prets|prêts|utilisable|disponible)\b.*\b(trait|transform)\w*", lowered)
        or re.search(r"\blots?\b.*\b(disponible|disponibles|pret|prêt|prets|prêts)\b.*\b(post-?recolte|post-récolte)\b", lowered)
    )
    asks_low_remaining_qty = bool(
        re.search(r"\b(peu|faible|petite)\b.{0,24}\b(quantite|quantité|restante?|reste)\b", lowered)
        or ("quantite restante" in lowered)
        or ("quantité restante" in lowered)
    )
    if asks_available_lots and asks_low_remaining_qty:
        entities["sort_by"] = "current_qty"
        entities["sort_order"] = "asc"
    asks_stock = bool(re.search(r"\bstock(?:s)?\b", lowered_ascii)) or ("inventaire" in lowered_ascii) or ("stockable" in lowered_ascii)
    if not asks_stock and not asks_available_lots and (
        any(token in lowered_ascii for token in ("combien", "reste", "restant", "restante", "disponible", "disponibles", "quantite disponible", "quantité disponible"))
        and (
            bool(entities.get("product"))
            or any(token in lowered_ascii for token in ("mangue", "mil", "arachide", "bissap", "produit", "produits", "kg", "kilogramme", "kilogrammes"))
        )
    ):
        asks_stock = True
    asks_stock_threshold = any(token in lowered_ascii for token in ("seuil", "rupture", "sous le seuil", "proche du seuil", "risque de rupture"))
    asks_stock_movements = asks_stock and any(
        token in lowered_ascii
        for token in ("mouvement", "mouvements", "journal", "historique", "nature", "origine")
    )
    asks_stock_direction = any(
        token in lowered_ascii
        for token in ("sortie", "sorties", "sortant", "sortants", "entrant", "entrants", "entree", "entrees", "entrée", "entrées")
    )
    if asks_stock and asks_stock_direction:
        asks_stock_movements = True
        if any(token in lowered_ascii for token in ("sortie", "sorties", "sortant", "sortants")):
            entities["movement_direction"] = "out"
        elif any(token in lowered_ascii for token in ("entrant", "entrants", "entree", "entrees", "entrée", "entrées")):
            entities["movement_direction"] = "in"
    if not asks_stock:
        stock_axes_tokens = ("total", "reserve", "reservee", "reservees", "disponible", "disponibles", "restant", "restante", "restantes")
        stock_axes_hits = sum(1 for token in stock_axes_tokens if token in lowered_ascii)
        if stock_axes_hits >= 2 and any(token in lowered_ascii for token in ("produit", "produits", "grade", "quantite", "quantites")):
            asks_stock = True
    asks_preharvest = any(token in lowered for token in ("pré-récolte", "pre-recolte", "pre-harvest", "parcelle", "parcelles", "lifecycle"))
    asks_ranking = any(
        token in lowered
        for token in (
            "plus élev",
            "plus eleve",
            "plus fortes",
            "plus fort",
            "plus grand",
            "top",
            "classement",
            "classe ",
            "ranking",
            "worst",
            "pire",
            "moins",
            "pourcentage",
            "taux de perte",
        )
    )
    explicit_loss_analytics = asks_loss or asks_gap or any(
        token in lowered for token in ("classement par perte", "taux de perte", "rendement", "efficacité", "efficacite")
    )
    explicit_no_loss = any(
        token in lowered for token in ("sans parler des pertes", "sans analyse de perte", "sans perte", "pas les pertes", "pas de pertes")
    )
    asks_stage_loss = any(
        token in lowered_ascii
        for token in (
            "a quelle etape",
            "quelle etape",
            "etape perd le plus",
            "plus mauvaise efficacite",
            "pire efficacite",
            "process-step",
            "process step",
            "etape la plus penalisante",
            "etape moins efficace",
            "pertes par etape",
            "perte par etape",
            "plus de pertes par etape",
        )
    ) and any(token in lowered_ascii for token in ("etape", "tri", "sechage", "nettoyage", "emballage", "conditionnement", "process"))
    asks_stage_loss = asks_stage_loss or bool(
        re.search(r"\b(etape|process)\b.*\b(plus|pire|moins)\b.*\b(perte|penalis|efficac|kg)\b", lowered_ascii)
        or re.search(r"\bpertes?\b.*\bpar\s+etapes?\b", lowered_ascii)
        or re.search(r"\bclasse\w*\b.*\betapes?\b.*\bpertes?\b", lowered_ascii)
    )
    asks_lot_comparison = (
        any(token in lowered for token in ("compare", "compar", "versus", " vs ", "entre "))
        and len(re.findall(r"\b(?:LOT|BATCH|MANG|MANGO|ARA|ARACH|MIL|BISS)[-_][A-Z0-9][A-Z0-9\-_]*\b", lowered, flags=re.IGNORECASE)) >= 2
    )
    asks_lot_specific_recommendation = asks_recommendation and (
        has_batch
        or bool(re.search(r"\b(?:lot|batch)[-_][a-z0-9][a-z0-9\-_]*\b", lowered))
    )
    asks_lot_specific_recommendation = asks_lot_specific_recommendation or (
        has_batch
        and (
            asks_recommendation
            or (
                asks_loss
                and any(
                    token in lowered
                    for token in (
                        "comment reduire",
                        "comment réduire",
                        "que faire",
                        "action",
                        "actions",
                        "recommand",
                        "sans inventer",
                    )
                )
            )
        )
    )
    asks_advisory_loss_process = (
        any(
            token in lowered
            for token in (
                "comment reduire les pertes",
                "comment réduire les pertes",
                "comment ameliorer le rendement",
                "comment améliorer le rendement",
                "que faire pour limiter les pertes",
                "pourquoi les pertes sont elevees",
                "pourquoi les pertes sont élevées",
                "conseils pour reduire les pertes",
                "conseils pour réduire les pertes",
            )
        )
        and any(token in lowered for token in ("sechage", "séchage", "tri", "emballage", "post-recolte", "post-récolte"))
    )
    if asks_advisory_loss_process and not has_batch and not asks_current_scope and not explicit_operational_metrics:
        asks_recommendation = False
    asks_lot_critical_ranking = has_lot_mention and any(
        token in lowered_ascii
        for token in (
            "lot critique",
            "lots critiques",
            "plus critique",
            "plus critiques",
            "lots a risque",
            "lot a risque",
            "top lots critiques",
        )
    )
    if not asks_recommendation and re.search(r"\bmesures?\s+(immediates?|immédiates?|a\s+lancer|à\s+lancer)\b", lowered_ascii) and (has_lot_mention or asks_loss or asks_risk):
        asks_recommendation = True
    asks_ml_log_status = (
        any(token in lowered_ascii for token in ("ml", "anomaly_score", "anomalie", "anomaly"))
        and any(token in lowered_ascii for token in ("combien", "nombre", "max", "maximum", "plus grand", "plus eleve", "top"))
        and not any(token in lowered_ascii for token in ("recommand", "action", "conseil", "pourquoi", "cause", "explique"))
        and not asks_current_scope
        and not any(token in lowered_ascii for token in ("perte", "efficac", "rendement", "etape", "sechage", "tri", "emballage", "conditionnement", "process"))
    )

    referential_marker = bool(FOLLOWUP_REFERENCE_PATTERN.search(lowered)) or any(
        token in lowered for token in ("same product", "meme produit", "même produit", "celui-ci", "celui ci", "et pour le meme produit", "et pour le même produit")
    )
    referential_followup = ((bool(previous_entities) or bool(previous_module_hint)) and referential_marker) or (
        referential_marker and asks_recommendation
    )
    if reset_context:
        referential_followup = False
    if referential_marker and not (previous_entities or previous_module_hint) and not has_batch:
        entities["intent_family"] = "FOLLOW_UP"
        entities["needs_batch_clarification"] = True
        return _decision(
            AgentRoute.SQL_ONLY,
            entities,
            ["SQLAnalyticsAgent"],
            "Ambiguous referential follow-up without prior entity must ask clarification.",
            0.84,
        )
    if referential_followup:
        if ("ce lot" in lowered or "pour ce lot" in lowered or "celui-ci" in lowered or "celui ci" in lowered) and not previous_entities.get("batch_ref") and not has_batch:
            entities["intent_family"] = "FOLLOW_UP"
            entities["needs_batch_clarification"] = True
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Lot follow-up requested without prior lot reference; clarification required.",
                0.85,
            )
        followup_recommendation_like = asks_recommendation or ("recommand" in lowered) or ("action" in lowered)
        if followup_recommendation_like and not previous_entities and not previous_module_hint and not has_batch:
            entities["intent_family"] = "FOLLOW_UP"
            entities["needs_batch_clarification"] = True
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Follow-up recommendation without previous lot context requires explicit lot clarification.",
                0.86,
            )
        safe_to_reuse = not (
            (entities.get("product") and previous_entities.get("product") and entities.get("product") != previous_entities.get("product"))
            or (entities.get("module") and previous_entities.get("module") and entities.get("module") != "global" and previous_entities.get("module") != "global" and entities.get("module") != previous_entities.get("module"))
        )
        if followup_recommendation_like and (
            previous_entities.get("batch_ref")
            or str(previous_entities.get("module") or "") in {"post_harvest", "material_balance", "recommendations"}
            or str(previous_module_hint or "") in {"post_harvest", "material_balance", "recommendations"}
        ):
            safe_to_reuse = True
        entities["intent_family"] = "FOLLOW_UP"
        if not safe_to_reuse:
            return _decision(AgentRoute.SQL_ONLY, entities, ["SQLAnalyticsAgent"], "Follow-up detected with context shift; avoid unsafe entity carry-over.", 0.84)
        if followup_recommendation_like:
            return _decision(
                AgentRoute.HYBRID_FULL,
                entities,
                ["SQLAnalyticsAgent", "MLLossAgent", "RAGKnowledgeAgent", "RecommendationAgent"],
                "Follow-up recommendation request.",
                0.88,
            )
        if asks_risk:
            return _decision(
                AgentRoute.HYBRID_SQL_ML,
                entities,
                ["SQLAnalyticsAgent", "MLLossAgent"],
                "Follow-up risk request.",
                0.87,
            )
        if asks_best_practice or asks_why:
            return _decision(
                AgentRoute.HYBRID_SQL_RAG,
                entities,
                ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
                "Follow-up explanatory request.",
                0.86,
            )
        return _decision(AgentRoute.SQL_ONLY, entities, ["SQLAnalyticsAgent"], "Follow-up operational request.", 0.85)

    if asks_stock_threshold and not asks_recommendation and not asks_risk:
        entities["intent_family"] = "factual_sql"
        entities["module"] = "stocks"
        return _decision(
            AgentRoute.SQL_ONLY,
            entities,
            ["SQLAnalyticsAgent"],
            "Stock threshold/rupture wording should stay on SQL low-stock logic.",
            0.91,
        )

    if asks_stock and (asks_best_practice or asks_why) and not asks_risk and not asks_recommendation:
        entities["intent_family"] = "hybrid_analysis"
        entities["module"] = "stocks"
        return _decision(
            AgentRoute.HYBRID_SQL_RAG,
            entities,
            ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
            "Stock fact + advisory explanation should combine SQL and RAG.",
            0.9,
        )

    if asks_lot_comparison and not asks_risk:
        entities["intent_family"] = "LOT_COMPARISON"
        entities["module"] = "material_balance"
        return _decision(AgentRoute.SQL_ONLY, entities, ["SQLAnalyticsAgent"], "Lot comparison on canonical material balance.", 0.92)

    if asks_stage_loss and not asks_recommendation and not asks_risk:
        entities["intent_family"] = "STAGE_LOSS_ANALYSIS"
        entities["module"] = "post_harvest"
        return _decision(AgentRoute.SQL_ONLY, entities, ["SQLAnalyticsAgent"], "Stage/process loss analysis intent.", 0.91)

    asks_recent_producer_delivery = (
        any(token in lowered_ascii for token in ("producteur", "producteurs", "membre", "membres"))
        and "livr" in lowered_ascii
        and any(token in lowered_ascii for token in ("recent", "récen", "plus recent", "plus récemment", "plus recemment", "dernier", "derniere", "dernière"))
    )
    if asks_recent_producer_delivery:
        entities["intent_family"] = "FOLLOW_UP"
        entities["needs_recency_clarification"] = True
        return _decision(
            AgentRoute.SQL_ONLY,
            entities,
            ["SQLAnalyticsAgent"],
            "Latest-delivery-by-producer wording requires capability clarification; avoid quantity-based fallback.",
            0.89,
        )

    if asks_advisory_loss_process and not asks_risk:
        if not asks_current_scope and not has_batch and not explicit_operational_metrics:
            entities["intent_family"] = "BEST_PRACTICES"
            entities["module"] = "post_harvest"
            return _decision(
                AgentRoute.RAG_ONLY,
                entities,
                ["RAGKnowledgeAgent"],
                "Advisory post-harvest loss wording without measured-data scope should stay RAG.",
                0.9,
            )
        entities["intent_family"] = "EXPLANATION_CAUSAL"
        entities["module"] = "post_harvest"
        return _decision(
            AgentRoute.HYBRID_SQL_RAG,
            entities,
            ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
            "Advisory loss/process question requires SQL grounding plus RAG advice.",
            0.9,
        )

    if asks_stock_movements and not asks_best_practice and not asks_why and not asks_risk and not asks_recommendation:
        entities["intent_family"] = "factual_sql"
        entities["module"] = "stocks"
        return _decision(AgentRoute.SQL_ONLY, entities, ["SQLAnalyticsAgent"], "Stock movement journal intent.", 0.92)

    if asks_stock and not asks_available_lots and not asks_best_practice and not asks_why and not asks_risk and not asks_recommendation:
        entities["intent_family"] = "STOCK_CURRENT"
        return _decision(AgentRoute.SQL_ONLY, entities, ["SQLAnalyticsAgent"], "Current stock intent.", 0.93)

    if asks_available_lots and (not explicit_loss_analytics or explicit_no_loss) and not asks_risk:
        entities["intent_family"] = "POSTHARVEST_AVAILABLE_LOTS"
        entities["module"] = "post_harvest"
        return _decision(AgentRoute.SQL_ONLY, entities, ["SQLAnalyticsAgent"], "Available post-harvest lots intent.", 0.93)

    if (asks_loss and asks_ranking and not asks_gap_by_qty and not asks_risk and not asks_recommendation and not asks_best_practice) or (
        asks_lot_critical_ranking and not asks_risk and not asks_recommendation
    ):
        entities["intent_family"] = "LOSS_RANKING"
        entities["module"] = "post_harvest"
        return _decision(AgentRoute.SQL_ONLY, entities, ["SQLAnalyticsAgent"], "Loss/efficiency ranking intent.", 0.92)

    if asks_gap and not asks_risk:
        entities["intent_family"] = "INPUT_OUTPUT_GAP"
        entities["module"] = "material_balance"
        return _decision(AgentRoute.SQL_ONLY, entities, ["SQLAnalyticsAgent"], "Input-output gap intent.", 0.92)

    if any(token in lowered_ascii for token in ("producteurs actifs", "membres actifs", "producteur actifs")) and any(
        token in lowered_ascii for token in ("parcelle", "parcelles", "produit", "produits")
    ):
        entities["intent_family"] = "factual_sql"
        entities["module"] = "members"
        return _decision(AgentRoute.SQL_ONLY, entities, ["SQLAnalyticsAgent"], "Active producers with parcel/product intent.", 0.9)

    if asks_preharvest and not asks_risk and not asks_recommendation:
        entities["intent_family"] = "PREHARVEST_STEPS"
        entities["module"] = "pre_harvest"
        return _decision(AgentRoute.SQL_ONLY, entities, ["SQLAnalyticsAgent"], "Pre-harvest lifecycle intent.", 0.9)

    if asks_best_practice and not asks_risk and not asks_recommendation and not asks_current_scope and not has_batch:
        entities["intent_family"] = "BEST_PRACTICES"
        return _decision(AgentRoute.RAG_ONLY, entities, ["RAGKnowledgeAgent"], "Pure best-practices intent.", 0.9)

    if asks_best_practice and not asks_risk and not asks_recommendation and not explicit_loss_analytics:
        entities["intent_family"] = "BEST_PRACTICES"
        if asks_current_scope or has_batch:
            return _decision(AgentRoute.HYBRID_SQL_RAG, entities, ["SQLAnalyticsAgent", "RAGKnowledgeAgent"], "Advice with current operational scope.", 0.88)
        return _decision(AgentRoute.RAG_ONLY, entities, ["RAGKnowledgeAgent"], "General best-practices intent.", 0.9)

    if asks_ml_log_status:
        entities["intent_family"] = "risk_ml"
        entities["module"] = "ml_logs"
        return _decision(AgentRoute.ML_ONLY, entities, ["MLLossAgent"], "Pure ML-log status intent.", 0.91)

    ml_signal_like = (
        any(token in lowered_ascii for token in ("signaux ml", "signal ml", "alertes ml", "alerte ml", "anomaly_score", "anomal", "risque ml"))
        and ("ml" in lowered_ascii or "anomaly_score" in lowered_ascii)
    )
    if ml_signal_like and not asks_recommendation and not asks_best_practice and not asks_current_scope and not has_batch:
        entities["intent_family"] = "risk_ml"
        entities["module"] = "ml_risk"
        return _decision(
            AgentRoute.HYBRID_SQL_ML,
            entities,
            ["SQLAnalyticsAgent", "MLLossAgent"],
            "ML risk-signal wording should combine ML signals with SQL operational context.",
            0.9,
        )

    if any(token in lowered_ascii for token in ("tresorerie", "transaction", "transactions")) and any(
        token in lowered_ascii for token in ("justificatif", "recu", "receipt", "reference", "preuve")
    ):
        entities["intent_family"] = "factual_sql"
        entities["module"] = "finance"
        return _decision(AgentRoute.SQL_ONLY, entities, ["SQLAnalyticsAgent"], "Treasury traceability intent.", 0.91)

    if asks_risk:
        entities["intent_family"] = "RISK_ANALYSIS"
        return _decision(AgentRoute.HYBRID_SQL_ML, entities, ["SQLAnalyticsAgent", "MLLossAgent"], "Risk/anomaly intent.", 0.92)

    if asks_lot_specific_recommendation:
        entities["intent_family"] = "LOT_SPECIFIC_RECOMMENDATION"
        return _decision(
            AgentRoute.HYBRID_FULL,
            entities,
            ["SQLAnalyticsAgent", "MLLossAgent", "RAGKnowledgeAgent", "RecommendationAgent"],
            "Lot-specific recommendation intent.",
            0.9,
        )

    if asks_recommendation:
        if not has_batch and re.search(r"\b(lot|batch)\b", lowered_ascii) and not asks_lot_critical_ranking:
            entities["intent_family"] = "FOLLOW_UP"
            entities["needs_batch_clarification"] = True
            return _decision(
                AgentRoute.SQL_ONLY,
                entities,
                ["SQLAnalyticsAgent"],
                "Recommendation request mentions lot/batch but no explicit reference; clarification required.",
                0.88,
            )
        entities["intent_family"] = "RECOMMENDATION"
        if asks_current_scope or has_operational_anchor or asks_loss or asks_risk or (
            has_lot_mention and any(token in lowered_ascii for token in ("critique", "perte", "efficac", "rendement", "risque", "a risque"))
        ):
            return _decision(
                AgentRoute.HYBRID_FULL,
                entities,
                ["SQLAnalyticsAgent", "MLLossAgent", "RAGKnowledgeAgent", "RecommendationAgent"],
                "Operational recommendation intent.",
                0.9,
            )
        return _decision(
            AgentRoute.RECOMMENDATION_ONLY,
            entities,
            ["RecommendationAgent"],
            "Generic recommendation intent.",
            0.82,
        )

    if asks_why and (has_batch or asks_loss):
        entities["intent_family"] = "EXPLANATION_CAUSAL"
        if asks_risk:
            return _decision(
                AgentRoute.HYBRID_SQL_ML,
                entities,
                ["SQLAnalyticsAgent", "MLLossAgent"],
                "Causal explanation with explicit risk framing.",
                0.88,
            )
        return _decision(
            AgentRoute.HYBRID_SQL_RAG,
            entities,
            ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
            "Causal explanation intent.",
            0.88,
        )

    return None

def _infer_previous_module_hint(
    previous_user_query: str | None,
    entity_extractor: EntityExtractor,
    *,
    known_batch_refs: set[str] | None = None,
) -> str | None:
    text = str(previous_user_query or "").strip()
    if not text:
        return None
    extracted = entity_extractor.extract(text, known_batch_refs=known_batch_refs).as_dict()
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
