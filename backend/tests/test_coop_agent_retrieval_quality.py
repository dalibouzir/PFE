from app.ai.retrieval.query_rewriter import rewrite_query
from app.ai.retrieval.reranker import rerank_chunks


def _candidate(*, title: str, content: str, product: str, stage: str, topic: str, hybrid_score: float):
    return {
        "document_id": f"doc-{title}",
        "chunk_id": f"chunk-{title}",
        "title": title,
        "content": content,
        "metadata": {
            "product": product,
            "stage": stage,
            "topic": topic,
            "language": "fr",
        },
        "hybrid_score": hybrid_score,
    }


def test_drying_mango_query_boosts_stage_and_product():
    query = "Comment réduire les pertes au séchage de la mangue ?"
    rewritten = rewrite_query(query)
    assert "séchage" in rewritten["expanded_domain_query"] or "sechage" in rewritten["expanded_domain_query"]

    ranked = rerank_chunks(
        [
            _candidate(
                title="Drying Best Practices",
                content="Réduction des pertes au séchage pour mangue.",
                product="mango",
                stage="drying",
                topic="loss_reduction",
                hybrid_score=0.62,
            ),
            _candidate(
                title="Packaging Generic",
                content="Bonnes pratiques emballage.",
                product="general",
                stage="packaging",
                topic="quality",
                hybrid_score=0.70,
            ),
        ],
        detected_entities={"product": ["mango"], "stage": ["drying"], "metric": ["loss"]},
        top_k=2,
    )
    top = ranked[0]
    assert top["metadata"]["stage"] == "drying"
    assert top["metadata"]["product"] == "mango"


def test_material_balance_query_prefers_material_balance_topic():
    ranked = rerank_chunks(
        [
            _candidate(
                title="Material Balance Guide",
                content="Bilan matière input output pertes.",
                product="general",
                stage="general",
                topic="material_balance",
                hybrid_score=0.58,
            ),
            _candidate(
                title="General Storage",
                content="Conseils de stockage.",
                product="general",
                stage="storage",
                topic="quality",
                hybrid_score=0.60,
            ),
        ],
        detected_entities={"product": [], "stage": [], "metric": ["material_balance"]},
        top_k=2,
    )
    assert ranked[0]["metadata"]["topic"] == "material_balance"


def test_sorting_query_prefers_sorting_stage():
    ranked = rerank_chunks(
        [
            _candidate(
                title="Sorting Losses",
                content="Pourquoi le tri génère des pertes.",
                product="mango",
                stage="sorting",
                topic="loss_reduction",
                hybrid_score=0.57,
            ),
            _candidate(
                title="Cleaning",
                content="Nettoyage.",
                product="mango",
                stage="cleaning",
                topic="quality",
                hybrid_score=0.64,
            ),
        ],
        detected_entities={"product": ["mango"], "stage": ["sorting"], "metric": ["loss"]},
        top_k=2,
    )
    assert ranked[0]["metadata"]["stage"] == "sorting"


def test_packaging_risk_query_prefers_packaging_stage():
    ranked = rerank_chunks(
        [
            _candidate(
                title="Packaging Risks",
                content="Risques pendant l'emballage.",
                product="millet",
                stage="packaging",
                topic="risk",
                hybrid_score=0.54,
            ),
            _candidate(
                title="Drying Notes",
                content="Séchage.",
                product="millet",
                stage="drying",
                topic="risk",
                hybrid_score=0.60,
            ),
        ],
        detected_entities={"product": ["millet"], "stage": ["packaging"], "metric": ["risk"]},
        top_k=2,
    )
    assert ranked[0]["metadata"]["stage"] == "packaging"
