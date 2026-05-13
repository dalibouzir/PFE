from __future__ import annotations

import re
import unicodedata


def rewrite_query(query: str) -> dict:
    original = str(query or "").strip()
    normalized = " ".join(unicodedata.normalize("NFKC", original).lower().split())
    keywords = _extract_keywords(normalized)

    expanded = normalized
    if "séchage" in expanded or "sechage" in expanded or "drying" in expanded:
        expanded += " pertes élevées humidité température durée séchage post-récolte"
    if "tri" in expanded or "sorting" in expanded:
        expanded += " tri post-récolte réduction pertes qualité"
    if "emballage" in expanded or "packaging" in expanded:
        expanded += " emballage conditionnement stockage risques qualité"
    if "bilan matière" in expanded or "bilan matiere" in expanded or "material balance" in expanded:
        expanded += " bilan matière input output pertes efficacité traçabilité"

    return {
        "original_query": original,
        "normalized_query": normalized,
        "expanded_domain_query": expanded,
        "keywords": keywords,
    }


def _extract_keywords(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9éèêàùç\-]+", text)
    stop = {
        "le",
        "la",
        "les",
        "de",
        "du",
        "des",
        "et",
        "pour",
        "the",
        "and",
        "what",
        "quel",
        "quelle",
        "quels",
        "quelles",
        "est",
        "sont",
        "dans",
        "why",
        "how",
    }
    return [tok for tok in tokens if tok not in stop][:20]
