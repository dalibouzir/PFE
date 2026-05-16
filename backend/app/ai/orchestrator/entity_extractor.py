from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


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
    "stockage": "storage",
    "storage": "storage",
}
NORMAL_FRENCH_REFERENCE_STOPWORDS = {
    "AVONS",
    "NOUS",
    "AVONS-NOUS",
    "QUEL",
    "QUELLE",
    "COMMENT",
    "POURQUOI",
    "DONNE",
    "ANALYSE",
    "RISQUE",
    "RISQUES",
    "STOCK",
    "PERTE",
    "PERTES",
    "LOT",
    "LOTS",
    "ETAPE",
    "ÉTAPE",
}

DATE_RANGE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
EXPLICIT_BATCH_PATTERN = re.compile(r"\b(?:LOT|BATCH)[-_][A-Z0-9][A-Z0-9\-_]*\b", re.IGNORECASE)
PRODUCT_BATCH_PATTERN = re.compile(r"\b(?:MANG|MANGO|ARA|ARACH|MIL|BISS)[-_]\d{2,5}\b", re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9\-_]*")
SPACED_PRODUCT_BATCH_PATTERN = re.compile(r"\b([A-Za-z]{3,8})\s*[-_ ]\s*(\d{2,5})\b", re.IGNORECASE)
TEXT_NORMALIZATION_REPLACEMENTS = {
    "sitation": "situation",
}


@dataclass
class ExtractedEntities:
    product: list[str] = field(default_factory=list)
    stage: list[str] = field(default_factory=list)
    batch_ref: str | None = None
    batch_ref_candidate: str | None = None
    specific_batch_requested: bool = False
    member_name: str | None = None
    date_range: list[str] = field(default_factory=list)
    metric: list[str] = field(default_factory=list)
    language: str = "fr"
    scope: str = "global"
    module: str = "global"

    def as_dict(self) -> dict:
        return {
            "product": self.product,
            "stage": self.stage,
            "batch_ref": self.batch_ref,
            "batch_ref_candidate": self.batch_ref_candidate,
            "specific_batch_requested": self.specific_batch_requested,
            "member_name": self.member_name,
            "date_range": self.date_range,
            "metric": self.metric,
            "language": self.language,
            "scope": self.scope,
            "module": self.module,
        }


class EntityExtractor:
    """Deterministic entity extraction for Phase 1 controlled app-data access."""

    def extract(self, query: str, *, language_hint: str | None = None, known_batch_refs: set[str] | None = None) -> ExtractedEntities:
        raw = str(query or "").strip()
        lowered = _normalize_for_detection(_normalize(raw).lower())
        known_refs = {str(value).upper() for value in (known_batch_refs or set()) if str(value).strip()}
        batch_ref, batch_candidate, specific_batch_requested = self._extract_batch_ref(raw, lowered, known_refs)

        scope = _detect_scope(lowered, batch_ref=batch_ref)
        metric = _detect_metrics(lowered)
        module = _detect_module(lowered, scope=scope, metric=metric)

        return ExtractedEntities(
            product=_detect_products(lowered),
            stage=_detect_stages(lowered),
            batch_ref=batch_ref,
            batch_ref_candidate=batch_candidate,
            specific_batch_requested=specific_batch_requested,
            member_name=_detect_member(raw),
            date_range=DATE_RANGE_PATTERN.findall(raw),
            metric=metric,
            language=_detect_language(lowered, language_hint),
            scope=scope,
            module=module,
        )

    def _extract_batch_ref(self, raw: str, lowered: str, known_refs: set[str]) -> tuple[str | None, str | None, bool]:
        candidates: list[str] = []
        candidates.extend(match.group(0).upper() for match in EXPLICIT_BATCH_PATTERN.finditer(raw))
        candidates.extend(match.group(0).upper() for match in PRODUCT_BATCH_PATTERN.finditer(raw))
        for match in SPACED_PRODUCT_BATCH_PATTERN.finditer(raw):
            prefix = str(match.group(1) or "").upper()
            suffix = str(match.group(2) or "").upper()
            if prefix and suffix:
                candidates.append(f"{prefix}-{suffix}")

        for token in _batch_lookup_candidates(raw):
            upper = token.upper().strip()
            if upper in known_refs and upper not in NORMAL_FRENCH_REFERENCE_STOPWORDS:
                return upper, upper, True
        for token in _batch_lookup_candidates(raw):
            upper = token.upper().strip()
            if not _looks_like_lot_token(upper):
                continue
            fuzzy_match = _best_fuzzy_known_ref(upper, known_refs)
            if fuzzy_match:
                return fuzzy_match, upper, True

        candidates = [candidate for candidate in candidates if _is_allowed_batch_candidate(candidate)]
        if candidates:
            return candidates[0], candidates[0], True

        # A clearly lot-specific request with an invalid-looking candidate is kept only as a candidate.
        if re.search(r"\b(lot|batch)\b", lowered):
            for token in TOKEN_PATTERN.findall(raw):
                upper = token.upper()
                if "-" in upper and upper not in NORMAL_FRENCH_REFERENCE_STOPWORDS:
                    return None, upper, False

        return None, None, False


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _normalize_for_detection(text: str) -> str:
    value = str(text or "")
    for wrong, fixed in TEXT_NORMALIZATION_REPLACEMENTS.items():
        value = re.sub(rf"(?<!\w){re.escape(wrong)}(?!\w)", fixed, value, flags=re.IGNORECASE)
    return value


def _is_allowed_batch_candidate(candidate: str) -> bool:
    upper = candidate.upper().strip()
    if upper in NORMAL_FRENCH_REFERENCE_STOPWORDS:
        return False
    return bool(EXPLICIT_BATCH_PATTERN.fullmatch(upper) or PRODUCT_BATCH_PATTERN.fullmatch(upper))


def _detect_products(text: str) -> list[str]:
    detected = {canonical for token, canonical in PRODUCT_MAP.items() if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text)}

    normalized_tokens = [_normalize_token_for_fuzzy(token) for token in TOKEN_PATTERN.findall(text)]
    for token in normalized_tokens:
        if len(token) < 4:
            continue
        for key, canonical in PRODUCT_MAP.items():
            key_norm = _normalize_token_for_fuzzy(key)
            if len(key_norm) < 4:
                continue
            if token[:1] != key_norm[:1]:
                continue
            if _is_edit_distance_leq_one(token, key_norm):
                detected.add(canonical)
    return sorted(detected)


def _detect_stages(text: str) -> list[str]:
    return sorted({canonical for token, canonical in STAGE_MAP.items() if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text)})


def _detect_member(text: str) -> str | None:
    match = re.search(r"(?:membre|member|farmer|producteur)\s+([A-Za-zÀ-ÿ][\w\- ]{1,60})", text or "", re.IGNORECASE)
    if not match:
        return None
    candidate = match.group(1).strip()
    lowered = candidate.lower()
    invalid_starts = (
        "a ",
        "au ",
        "aux ",
        "de ",
        "du ",
        "des ",
        "le ",
        "la ",
        "les ",
        "qui ",
        "avec ",
        "sont ",
        "est ",
        "a ",
        "ont ",
        "code ",
    )
    if any(lowered.startswith(prefix) for prefix in invalid_starts):
        return None
    return candidate


def _detect_metrics(text: str) -> list[str]:
    metric_map = {
        "perte": "loss",
        "loss": "loss",
        "efficacite": "efficiency",
        "efficacité": "efficiency",
        "efficiency": "efficiency",
        "stock": "stock",
        "collecte": "collection",
        "collectée": "collection",
        "collectee": "collection",
        "collecté": "collection",
        "collecté": "collection",
        "quantité reçue": "collection",
        "quantite recue": "collection",
        "livré": "collection",
        "livre": "collection",
        "total collecté": "collection",
        "total collecte": "collection",
        "anomal": "anomaly",
        "risque": "risk",
        "risk": "risk",
        "anomaly_score": "anomaly",
        "signaux ml": "ml_signal",
        "signal ml": "ml_signal",
        "logs ml": "ml_signal",
        "high": "ml_signal",
        "recommand": "recommendation",
        "facture": "invoice",
        "invoice": "invoice",
        "commande": "commercial_order",
        "vente": "commercial",
        "commercial": "commercial",
        "chiffre d'affaires": "revenue",
        "chiffre d’affaires": "revenue",
        "revenu": "revenue",
        "trésorerie": "finance",
        "tresorerie": "finance",
        "charge": "finance",
        "dépense": "finance",
        "depense": "finance",
        "coût": "cost",
        "cout": "cost",
        "valeur": "value",
    }
    detected: set[str] = set()
    for key, value in metric_map.items():
        if " " in key or "'" in key or "’" in key:
            if key in text:
                detected.add(value)
            continue
        if re.search(rf"\b{re.escape(key)}\b", text):
            detected.add(value)
    return sorted(detected)


def _detect_language(text: str, hint: str | None) -> str:
    if hint and str(hint).lower().strip() in {"fr", "en", "ar"}:
        return str(hint).lower().strip()
    english_markers = {"hello", "what", "why", "which", "batch", "drying"}
    return "en" if any(token in text for token in english_markers) else "fr"


def _detect_scope(text: str, *, batch_ref: str | None) -> str:
    if batch_ref:
        return "batch"
    if any(token in text for token in ("pré-récolte", "pre-harvest", "parcelle", "culture")):
        return "pre_harvest"
    if any(token in text for token in ("lot", "lots", "perte", "pertes", "séchage", "tri", "emballage", "post-récolte")):
        return "post_harvest"
    return "global"


def _detect_module(text: str, *, scope: str, metric: list[str]) -> str:
    if any(token in text for token in ("coopérative", "cooperative")) and any(
        token in text for token in ("résumé", "resume", "synthèse", "synthese", "aperçu", "apercu")
    ):
        return "cooperative_summary"
    if any(
        token in text
        for token in (
            "recommand",
            "action prioritaire",
            "actions prioritaires",
            "que faire",
            "on devrait faire quoi",
            "que doit on faire",
            "que doit-on faire",
            "comment améliorer",
            "comment ameliorer",
            "comment réduire",
            "mieux sécher",
            "mieux secher",
        )
    ):
        return "recommendations"
    if any(token in text for token in ("facture", "factures", "invoice", "invoices")):
        return "invoices"
    if any(token in text for token in ("commande", "commandes", "vente", "ventes", "commercialisation", "commercial")):
        return "commercial"
    if any(token in text for token in ("trésorerie", "tresorerie", "charge", "charges", "dépense", "depense", "finance")):
        return "finance"
    if any(token in text for token in ("valeur", "coût", "cout")) and any(token in text for token in ("membre", "membres", "producteur", "producteurs")):
        return "member_value"
    if any(token in text for token in ("membre", "membres", "member", "farmer", "producteur", "producteurs")):
        return "members"
    if any(
        token in text
        for token in (
            "collecte",
            "collectées",
            "collectee",
            "collectée",
            "collecté",
            "livré",
            "livre",
            "livrees",
            "quantité reçue",
            "quantite recue",
            "total collecté",
            "total collecte",
            "intrant",
            "inputs",
            "grade",
            "aujourd'hui",
            "aujourd’hui",
            "aujourdhui",
        )
    ):
        return "collections"
    if re.search(r"\bstock(s)?\b", text) or any(token in text for token in ("seuil critique", "seuil")):
        return "stocks"
    if "risk" in metric or "anomaly" in metric:
        return "ml_risk"
    if any(token in text for token in ("bilan matière", "bilan matiere", "material balance")):
        return "material_balance"
    if scope == "pre_harvest":
        return "pre_harvest"
    if scope in {"batch", "post_harvest"}:
        return "post_harvest"
    if any(
        token in text
        for token in (
            "explique",
            "bonnes pratiques",
            "meilleures pratiques",
            "best practices",
            "référence",
            "references",
            "comment réduire",
            "comment ameliorer",
            "comment améliorer",
            "humidite",
            "humidité",
            "stockage",
            "sechage",
            "séchage",
            "tri",
            "casse",
            "check-list",
            "checklist",
        )
    ):
        return "rag_knowledge"
    return "global"


def _batch_lookup_candidates(raw: str) -> list[str]:
    tokens = [str(token).upper() for token in TOKEN_PATTERN.findall(raw or "")]
    candidates: list[str] = []
    for idx, token in enumerate(tokens):
        if token:
            candidates.append(token)
        if idx + 1 < len(tokens):
            right = tokens[idx + 1]
            if token.isalpha() and right.isdigit():
                candidates.append(f"{token}-{right}")
    for match in SPACED_PRODUCT_BATCH_PATTERN.finditer(raw or ""):
        prefix = str(match.group(1) or "").upper()
        suffix = str(match.group(2) or "").upper()
        if prefix and suffix:
            candidates.append(f"{prefix}-{suffix}")
    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        cleaned = str(item).strip().upper()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


def _looks_like_lot_token(token: str) -> bool:
    value = str(token or "").upper().strip()
    return len(value) >= 5 and any(ch.isalpha() for ch in value) and any(ch.isdigit() for ch in value)


def _best_fuzzy_known_ref(candidate: str, known_refs: set[str]) -> str | None:
    if not known_refs:
        return None
    candidate_norm = _normalize_batch_key(candidate)
    if not candidate_norm:
        return None

    best: str | None = None
    for known in known_refs:
        known_norm = _normalize_batch_key(known)
        if not known_norm:
            continue
        if candidate_norm == known_norm:
            return known
        if candidate_norm[:3] != known_norm[:3]:
            continue
        if _is_edit_distance_leq_one(candidate_norm, known_norm):
            best = known
            break
    return best


def _normalize_batch_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _normalize_token_for_fuzzy(value: str) -> str:
    lowered = str(value or "").lower()
    normalized = unicodedata.normalize("NFKD", lowered)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _is_edit_distance_leq_one(left: str, right: str) -> bool:
    if left == right:
        return True
    if abs(len(left) - len(right)) > 1:
        return False

    if len(left) == len(right):
        mismatches = sum(1 for lch, rch in zip(left, right) if lch != rch)
        if mismatches <= 1:
            return True
        if mismatches == 2:
            # Accept one transposition.
            for idx in range(len(left) - 1):
                if left[idx] != right[idx]:
                    swapped = list(left)
                    swapped[idx], swapped[idx + 1] = swapped[idx + 1], swapped[idx]
                    return "".join(swapped) == right
        return False

    if len(left) < len(right):
        left, right = right, left
    # left is longer by exactly one character.
    i = 0
    j = 0
    edits = 0
    while i < len(left) and j < len(right):
        if left[i] == right[j]:
            i += 1
            j += 1
            continue
        edits += 1
        if edits > 1:
            return False
        i += 1
    return True
