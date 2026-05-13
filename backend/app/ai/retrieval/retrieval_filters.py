from __future__ import annotations


def build_retrieval_filters(detected_entities: dict) -> dict:
    product_values = detected_entities.get("product") or []
    stage_values = detected_entities.get("stage") or []
    language = detected_entities.get("language") or "fr"
    batch_ref = detected_entities.get("batch_ref")

    return {
        "product": set(product_values),
        "stage": set(stage_values),
        "language": language,
        "batch_ref": batch_ref,
    }


def metadata_boost(item: dict, filters: dict) -> float:
    score = 0.0
    metadata = item.get("metadata") or {}

    products = filters.get("product") or set()
    stages = filters.get("stage") or set()

    if products:
        meta_product = str(metadata.get("product") or metadata.get("product_name") or metadata.get("crop") or "").lower()
        if meta_product in products:
            score += 0.2

    if stages:
        meta_stage = str(metadata.get("stage") or metadata.get("stage_canonical") or "").lower()
        if meta_stage in stages:
            score += 0.2

    lang = str(filters.get("language") or "fr").lower()
    meta_lang = str(metadata.get("language") or "").lower()
    if meta_lang and meta_lang == lang:
        score += 0.05

    if filters.get("batch_ref"):
        batch_ref = str(filters.get("batch_ref")).upper()
        candidate = str(metadata.get("batch_code") or metadata.get("batch_ref") or "").upper()
        if candidate == batch_ref:
            score += 0.2

    return score
