from __future__ import annotations

from typing import Any

PROMPT_INJECTION_MARKERS = (
    "ignore previous instructions",
    "reveal secrets",
    "change system behavior",
)


def format_chunks_for_llm(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    warnings: list[str] = []
    rendered: list[str] = []
    products: set[str] = set()
    stages: set[str] = set()

    for chunk in chunks:
        metadata = chunk.get("metadata") or {}
        product = str(metadata.get("product") or metadata.get("product_name") or "general").lower()
        stage = str(metadata.get("stage") or metadata.get("stage_canonical") or "general").lower()
        title = str(chunk.get("title") or "Source")
        score = float(chunk.get("final_score") or chunk.get("hybrid_score") or 0.0)
        content = str(chunk.get("content") or "")

        if any(marker in content.lower() for marker in PROMPT_INJECTION_MARKERS):
            warnings.append("PROMPT_INJECTION_DETECTED")
            continue

        products.add(product)
        stages.add(stage)

        rendered.append(
            f"[Source: {title} | product={product} | stage={stage} | score={score:.2f}]\n{content}"
        )

    if len(products) > 1 or len(stages) > 2:
        warnings.append("CONTRADICTORY_CONTEXT_POSSIBLE")

    return {"chunks": rendered, "warnings": sorted(set(warnings))}
