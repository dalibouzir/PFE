from datetime import date

from app.models.commercial_catalog_product import CommercialCatalogProduct
from app.models.commercial_order import CommercialOrder, CommercialOrderLine
from app.models.enums import (
    CommercialOrderStatus,
    MemberStatus,
    PreHarvestStepStatus,
    RiskLevel,
)
from app.models.global_charge import GlobalCharge
from app.models.member import Member
from app.models.ml import (
    MLModelRegistry,
    MLPredictionLog,
    MLRecommendationLog,
    MLTrainingRun,
    RecommendationFeedbackLog,
)
from app.models.parcel import Parcel
from app.models.pre_harvest_step import PreHarvestStep
from app.models.reference import KnowledgeChunk, ReferenceMetric
from app.models.recommendation import Recommendation
from app.models.rag import RAGChunk, RAGDocument
from app.models.user import User
from app.services.assistant import RetrievalHit, _rerank_hits
from app.services.rag_chunk_registry import get_registered_source_tables
from app.services.rag_indexer import (
    _collect_source_documents,
    _semantic_chunk_or_fallback,
    get_indexed_source_tables,
    reindex_cooperative,
)


def _seed_semantic_domain_rows(db_session):
    manager = db_session.query(User).first()
    cooperative = manager.cooperative
    product = cooperative.products[0]
    batch = cooperative.batches[0]

    member = Member(
        cooperative_id=cooperative.id,
        code="M-SEM-010",
        full_name="Semantic Domain Member",
        phone="+221770009900",
        village="Village Test",
        main_product=product.name,
        secondary_products=None,
        parcel_count=1,
        area_hectares=2.0,
        specialty="quality",
        status=MemberStatus.ACTIVE,
    )
    db_session.add(member)
    db_session.flush()

    parcel = Parcel(
        cooperative_id=cooperative.id,
        member_id=member.id,
        name="Parcel Semantic",
        surface_ha=1.3,
        main_culture=product.name,
        variety="Kent",
        tree_count=90,
    )
    db_session.add(parcel)
    db_session.flush()

    pre_step = PreHarvestStep(
        cooperative_id=cooperative.id,
        parcel_id=parcel.id,
        member_id=member.id,
        step_order=1,
        step_key="fertilization",
        category="nutrition",
        label="Fertilization NPK",
        icon="seed",
        status=PreHarvestStepStatus.COMPLETED,
        quantity_value=25.0,
        quantity_unit="kg",
        operation_cost_fcfa=18000.0,
        realization_date=date.today(),
        observations="Completed on schedule",
        created_by_user_id=manager.id,
    )
    db_session.add(pre_step)

    recommendation = Recommendation(
        batch_id=batch.id,
        loss_pct=12.0,
        efficiency_pct=88.0,
        anomaly_score=0.67,
        risk_level=RiskLevel.MEDIUM,
        suggested_action="Adjust drying airflow",
        rationale="Drying loss trend is rising",
    )
    db_session.add(recommendation)

    prediction = MLPredictionLog(
        batch_id=batch.id,
        model_version="v3.0",
        product=product.name,
        critical_stage="drying",
        predicted_loss_pct=13.7,
        expected_efficiency_pct=86.3,
        risk_level=RiskLevel.HIGH,
        anomaly_score=0.82,
        is_anomalous=True,
        input_snapshot={"trend": "loss_increase"},
        output_snapshot={"confidence": 0.79},
    )
    db_session.add(prediction)
    db_session.flush()

    recommendation_log = MLRecommendationLog(
        batch_id=batch.id,
        structured_recommendation={"action": "Check humidity", "risk_level": "HIGH"},
        llm_explanation="Drying stage variability is above normal.",
    )
    db_session.add(recommendation_log)
    db_session.flush()

    feedback = RecommendationFeedbackLog(
        recommendation_log_id=recommendation_log.id,
        batch_id=batch.id,
        stage="drying",
        context_snapshot={"signal": "high_loss"},
        recommendation_snapshot={"action": "Check humidity"},
        accepted=True,
        executed=True,
        delta_loss=-1.8,
        outcome_label="improved",
        model_version="v3.0",
        comment="Improved after process change",
    )
    db_session.add(feedback)

    charge = GlobalCharge(
        cooperative_id=cooperative.id,
        member_id=member.id,
        parcel_id=parcel.id,
        pre_harvest_step_id=pre_step.id,
        batch_id=batch.id,
        process_step_id=None,
        charge_type="labor",
        label="Field labor",
        amount_fcfa=22000.0,
        date=date.today(),
        notes="Seasonal labor",
        source_type="manual",
    )
    db_session.add(charge)

    training_run = MLTrainingRun(
        run_name="run-semantic-001",
        status="completed",
        dataset_rows=520,
        metrics={"rmse": 4.2, "model_version": "v3.0"},
    )
    db_session.add(training_run)
    db_session.flush()

    model_registry = MLModelRegistry(
        model_name="loss_regressor",
        version="v3.0",
        artifact_path="/tmp/loss_regressor_v3.joblib",
        metrics={"rmse": 4.2},
        is_active=True,
        training_run_id=training_run.id,
    )
    db_session.add(model_registry)

    knowledge = KnowledgeChunk(
        source_id="FAO-DRY-001",
        source_url="https://example.org/fao-drying",
        country="Senegal",
        region="Thies",
        crop="millet",
        topic="drying best practices",
        content="Drying losses increase with humidity and poor airflow.",
    )
    db_session.add(knowledge)

    reference_metric = ReferenceMetric(
        source_id="APHLIS-LOSS-001",
        country="Senegal",
        region="Thies",
        crop="millet",
        metric="post_harvest_loss_pct",
        period="2024",
        value=11.8,
        unit="%",
        notes="External benchmark value for comparison.",
    )
    db_session.add(reference_metric)

    catalog = CommercialCatalogProduct(
        cooperative_id=cooperative.id,
        source_product_id=product.id,
        name="Mango commercial",
        category="fruit",
        sale_unit="kg",
        sale_price_fcfa=1400.0,
        cost_price_fcfa=950.0,
        total_stock_kg=250.0,
        reserved_stock_kg=20.0,
    )
    db_session.add(catalog)
    db_session.flush()

    order = CommercialOrder(
        cooperative_id=cooperative.id,
        order_number="ORD-SEM-100",
        customer_name="Buyer A",
        status=CommercialOrderStatus.PREPARING,
        subtotal_fcfa=140000.0,
        tax_rate=0.18,
        tax_amount_fcfa=25200.0,
        total_amount_fcfa=165200.0,
        source="consumer_app",
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        CommercialOrderLine(
            order_id=order.id,
            catalog_product_id=catalog.id,
            product_name_snapshot=catalog.name,
            unit_snapshot="kg",
            quantity=100.0,
            quantity_kg=100.0,
            unit_price_fcfa=1400.0,
            line_total_fcfa=140000.0,
        )
    )

    db_session.commit()
    return cooperative.id


def test_registry_and_source_coverage_are_expanded():
    registered = set(get_registered_source_tables())
    assert "batches" in registered
    assert "process_steps" in registered
    assert "recommendations" in registered
    assert "parcels" in registered
    assert "pre_harvest_steps" in registered
    assert "ml_prediction_logs" in registered
    assert "recommendation_feedback_logs" in registered
    assert "knowledge_chunks" in registered
    assert "reference_metrics" in registered

    indexed = set(get_indexed_source_tables())
    for required in (
        "parcels",
        "pre_harvest_steps",
        "recommendations",
        "ml_prediction_logs",
        "ml_recommendation_logs",
        "recommendation_feedback_logs",
        "global_charges",
        "ml_training_runs",
        "ml_model_registry",
        "knowledge_chunks",
        "reference_metrics",
    ):
        assert required in indexed


def test_collect_source_documents_includes_new_semantic_domains(db_session):
    cooperative_id = _seed_semantic_domain_rows(db_session)
    docs = _collect_source_documents(db_session, cooperative_id)
    tables = {doc.source_table for doc in docs}
    assert "parcels" in tables
    assert "pre_harvest_steps" in tables
    assert "recommendations" in tables
    assert "ml_prediction_logs" in tables
    assert "ml_recommendation_logs" in tables
    assert "recommendation_feedback_logs" in tables
    assert "global_charges" in tables
    assert "ml_training_runs" in tables
    assert "ml_model_registry" in tables
    assert "knowledge_chunks" in tables
    assert "reference_metrics" in tables

    recommendation_docs = [doc for doc in docs if doc.source_table == "recommendations"]
    assert recommendation_docs
    assert any(doc.metadata.get("chunk_type") == "recommendation_context" for doc in recommendation_docs)
    assert any(doc.metadata.get("chunk_type") == "lot_recommendation_summary" for doc in recommendation_docs)

    anomaly_docs = [doc for doc in docs if doc.metadata.get("chunk_type") == "anomaly_summary"]
    assert anomaly_docs

    process_docs = [doc for doc in docs if doc.source_table == "process_steps"]
    assert any(doc.metadata.get("chunk_type") == "product_stage_summary" for doc in process_docs)
    assert any(doc.metadata.get("chunk_type") == "scoped_loss_summary" for doc in process_docs)

    batch_docs = [doc for doc in docs if doc.source_table == "batches"]
    assert any(doc.metadata.get("chunk_type") == "lot_status_summary" for doc in batch_docs)
    assert any(doc.metadata.get("chunk_type") == "operational_risk_summary" for doc in batch_docs)

    knowledge_docs = [doc for doc in docs if doc.source_table == "knowledge_chunks"]
    assert knowledge_docs
    assert any(doc.metadata.get("chunk_type") == "agronomic_knowledge" for doc in knowledge_docs)

    benchmark_docs = [doc for doc in docs if doc.source_table == "reference_metrics"]
    assert benchmark_docs
    assert any(doc.metadata.get("chunk_type") == "benchmark_reference" for doc in benchmark_docs)


def test_fallback_chunking_still_works():
    content, metadata = _semantic_chunk_or_fallback(
        source_table="unknown_table",
        fallback_content="Legacy fallback content",
        fallback_metadata={"entity": "legacy"},
        builder_kwargs={},
    )
    assert content == "Legacy fallback content"
    assert metadata == {"entity": "legacy"}


def test_rerank_with_chunk_type_boost_preserves_retrieval_results():
    hits = [
        RetrievalHit(
            chunk_id="1",
            source_table="recommendations",
            source_record_ref="recommendation:1",
            content="Recommendation context for anomaly mitigation",
            metadata={"chunk_type": "recommendation_context"},
            distance=0.3,
            keyword_score=0.5,
            vector_rank=1,
            keyword_rank=2,
        ),
        RetrievalHit(
            chunk_id="2",
            source_table="batches",
            source_record_ref="batch:2",
            content="Batch operational summary",
            metadata={"chunk_type": "batch_summary"},
            distance=0.4,
            keyword_score=0.4,
            vector_rank=2,
            keyword_rank=1,
        ),
    ]
    ranked = _rerank_hits(message="why risk anomaly recommendation", hits=hits, limit=2)
    assert len(ranked) == 2
    assert ranked[0].rerank_score >= ranked[1].rerank_score


def test_forced_reindex_includes_reference_chunk_types(db_session, monkeypatch):
    cooperative_id = _seed_semantic_domain_rows(db_session)
    manager = db_session.query(User).first()
    monkeypatch.setattr("app.services.rag_indexer.embed_texts", lambda texts: [[0.0] * 1536 for _ in texts])

    response = reindex_cooperative(
        db_session,
        current_user=manager,
        cooperative_id=cooperative_id,
        force=True,
    )
    assert response.documents_seen > 0

    rows = (
        db_session.query(RAGChunk.metadata_json, RAGDocument.source_table)
        .join(RAGDocument, RAGDocument.id == RAGChunk.document_id)
        .filter(RAGDocument.source_table.in_(["knowledge_chunks", "reference_metrics"]))
        .all()
    )
    assert rows
    chunk_types = {str((metadata or {}).get("chunk_type")) for metadata, _ in rows}
    assert "agronomic_knowledge" in chunk_types
    assert "benchmark_reference" in chunk_types

    scoped_rows = (
        db_session.query(RAGChunk.metadata_json, RAGDocument.source_table)
        .join(RAGDocument, RAGDocument.id == RAGChunk.document_id)
        .filter(RAGDocument.source_table.in_(["batches", "process_steps", "recommendations"]))
        .all()
    )
    scoped_types = {str((metadata or {}).get("chunk_type")) for metadata, _ in scoped_rows}
    assert "product_stage_summary" in scoped_types
    assert "lot_status_summary" in scoped_types
    assert "scoped_loss_summary" in scoped_types
