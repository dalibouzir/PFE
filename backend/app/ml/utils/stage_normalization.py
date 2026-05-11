from __future__ import annotations

import unicodedata


CANONICAL_STAGES = {"cleaning", "drying", "sorting", "packaging"}
STAGE_CANONICAL_MAP = {
    "nettoyage": "cleaning",
    "cleaning": "cleaning",
    "sechage": "drying",
    "sechage ": "drying",
    "séchage": "drying",
    "drying": "drying",
    "tri": "sorting",
    "sorting": "sorting",
    "emballage": "packaging",
    "conditionnement": "packaging",
    "packaging": "packaging",
}


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = " ".join(str(value).strip().split())
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def normalize_stage(value: str | None) -> str:
    normalized = _normalize_text(value)
    if not normalized:
        return "unknown"
    return STAGE_CANONICAL_MAP.get(normalized, "unknown")


def is_known_stage(value: str | None) -> bool:
    return normalize_stage(value) in CANONICAL_STAGES
