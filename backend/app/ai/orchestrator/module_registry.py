from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ModuleCapability:
    key: str
    label_fr: str
    keywords: tuple[str, ...]


class ModuleRegistry:
    """Lightweight capability map used for generalized routing and module targeting."""

    def __init__(self) -> None:
        self._modules: tuple[ModuleCapability, ...] = (
            ModuleCapability("members", "membres", ("membre", "membres", "member", "farmer", "producteur", "producteurs")),
            ModuleCapability("parcels", "parcelles", ("parcelle", "parcelles", "parcel", "pré-récolte", "pre-harvest", "culture")),
            ModuleCapability("inputs", "collectes", ("collecte", "collectes", "input", "intrant", "quantité collectée")),
            ModuleCapability("stocks", "stocks", ("stock", "stocks", "disponible", "reserved", "réservé", "seuil")),
            ModuleCapability("lots", "lots", ("lot", "lots", "batch", "bilan matière", "bilan matiere")),
            ModuleCapability("process_steps", "étapes de process", ("étape", "etape", "process", "séchage", "sechage", "tri", "nettoyage", "emballage")),
            ModuleCapability("material_balance", "bilan matière", ("bilan matière", "bilan matiere", "material balance", "rendement")),
            ModuleCapability("ml_logs", "signaux ML", ("ml", "anomal", "risque", "prediction", "prédiction")),
            ModuleCapability("rag", "bonnes pratiques", ("bonnes pratiques", "meilleures pratiques", "références", "references", "benchmark", "guidance")),
            ModuleCapability("recommendations", "recommandations", ("recommand", "actions prioritaires", "action prioritaire", "que faire", "plan d'action")),
            ModuleCapability("commercial", "commercialisation", ("commande", "commandes", "vente", "commercial", "catalogue")),
            ModuleCapability("invoices", "facturation", ("facture", "factures", "invoice", "invoices")),
            ModuleCapability("finance", "finance", ("finance", "trésorerie", "tresorerie", "charge", "charges", "dépense", "depense", "coût", "cout")),
            ModuleCapability("cooperative_summary", "vue globale coopérative", ("vue globale", "résumé", "resume", "synthèse", "synthese", "aperçu", "apercu", "coopérative", "cooperative")),
        )

    @property
    def module_keys(self) -> set[str]:
        return {item.key for item in self._modules}

    def detect_module(self, text: str) -> str | None:
        lowered = _normalize_text(text)
        best_key: str | None = None
        best_hits = 0
        for module in self._modules:
            hits = 0
            for keyword in module.keywords:
                if " " in keyword:
                    if keyword in lowered:
                        hits += 1
                    continue
                if re.search(rf"\b{re.escape(keyword)}\b", lowered):
                    hits += 1
            if hits > best_hits:
                best_hits = hits
                best_key = module.key
        return best_key if best_hits > 0 else None

    def labels_for_supported_modules(self) -> list[str]:
        return [item.label_fr for item in self._modules]

    def is_small_talk(self, text: str) -> bool:
        lowered = _normalize_text(text).strip()
        if not lowered:
            return False
        if lowered in {"bonjour", "salut", "hello", "hi", "bonsoir", "ok", "merci", "coucou", "ca va", "ça va", "salut cava", "salut ca va"}:
            return True
        if re.fullmatch(r"(salut|bonjour|hello|hi)\s*(ca va|ça va|cava)?", lowered):
            return True
        if re.search(r"\b(merci|thanks)\b", lowered):
            return True
        return False

    def is_capability_question(self, text: str) -> bool:
        lowered = _normalize_text(text)
        patterns = (
            "que peux tu faire",
            "que peux-tu faire",
            "tu peux m'aider à faire quoi",
            "tu peux m’aider à faire quoi",
            "aide moi",
            "aide-moi",
            "what can you do",
            "help me",
            "comment tu peux m'aider",
            "de quoi tu es capable",
        )
        return any(pattern in lowered for pattern in patterns)

    def is_operational_topic(self, text: str, module_hint: str | None = None) -> bool:
        if module_hint and module_hint in self.module_keys:
            return True
        return self.detect_module(text) is not None

    def is_non_operational_topic(self, text: str) -> bool:
        lowered = _normalize_text(text)
        return any(
            token in lowered
            for token in (
                "football",
                "champions league",
                "nba",
                "bitcoin",
                "crypto",
                "film",
                "movie",
                "politique",
                "weather",
                "météo",
                "meteo",
                "new york",
                "tokyo",
            )
        )


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").lower().split())
