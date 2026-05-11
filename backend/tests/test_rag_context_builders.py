from datetime import date

from app.models.commercial_catalog_product import CommercialCatalogProduct
from app.models.commercial_order import CommercialOrder, CommercialOrderLine
from app.models.enums import CommercialOrderStatus, MemberStatus, PreHarvestStepStatus, RiskLevel
from app.models.global_charge import GlobalCharge
from app.models.member import Member
from app.models.ml import MLPredictionLog, MLRecommendationLog, MLTrainingRun, RecommendationFeedbackLog
from app.models.parcel import Parcel
from app.models.pre_harvest_step import PreHarvestStep
from app.models.process_step import ProcessStep
from app.models.recommendation import Recommendation
from app.models.user import User
from app.services.rag_context_builders import (
    build_anomaly_summary_chunk,
    build_batch_summary_chunk,
    build_commercial_order_chunk,
    build_global_charge_chunk,
    build_lot_recommendation_summary_chunk,
    build_lot_status_summary_chunk,
    build_ml_prediction_chunk,
    build_operational_risk_summary_chunk,
    build_parcel_chunk,
    build_pre_harvest_chunk,
    build_product_stage_summary_chunk,
    build_recommendation_chunk,
    build_scoped_loss_summary_chunk,
    validate_chunk_metadata,
)


def _seed_member_parcel_and_steps(db_session):
    manager = db_session.query(User).first()
    cooperative = manager.cooperative
    member = Member(
        cooperative_id=cooperative.id,
        code="M-SEM-001",
        full_name="Semantic Member",
        phone="+221770001122",
        village="Village Semantic",
        main_product="mango",
        secondary_products=None,
        parcel_count=1,
        area_hectares=2.5,
        specialty="drying",
        status=MemberStatus.ACTIVE,
    )
    db_session.add(member)
    db_session.flush()

    parcel = Parcel(
        cooperative_id=cooperative.id,
        member_id=member.id,
        name="Champ Nord",
        surface_ha=1.9,
        main_culture="mango",
        variety="Kent",
        tree_count=120,
    )
    db_session.add(parcel)
    db_session.flush()

    step = PreHarvestStep(
        cooperative_id=cooperative.id,
        parcel_id=parcel.id,
        member_id=member.id,
        step_order=1,
        step_key="phytosanitary",
        category="protection",
        label="Traitement phytosanitaire",
        icon="leaf",
        status=PreHarvestStepStatus.PENDING,
        quantity_value=2.0,
        quantity_unit="L",
        operation_cost_fcfa=15000.0,
        realization_date=date.today(),
        observations="Delayed due to rain",
        created_by_user_id=manager.id,
    )
    db_session.add(step)
    db_session.commit()
    return cooperative, member, parcel, step


def test_batch_recommendation_chunk_is_semantic_and_metadata_valid(db_session):
    manager = db_session.query(User).first()
    batch = manager.cooperative.batches[0]
    steps = db_session.query(ProcessStep).filter(ProcessStep.batch_id == batch.id).all()
    recommendation = Recommendation(
        batch_id=batch.id,
        loss_pct=13.5,
        efficiency_pct=86.5,
        anomaly_score=0.74,
        risk_level=RiskLevel.HIGH,
        suggested_action="Review drying duration and airflow",
        rationale="Drying trend is above historical average",
    )
    db_session.add(recommendation)
    db_session.commit()

    payload = build_batch_summary_chunk(
        batch=batch,
        product=batch.product,
        process_steps=steps,
        recommendation=recommendation,
        cooperative_id=batch.cooperative_id,
    )
    assert payload["content"]
    assert "Lot" in payload["content"]
    assert "risk" in payload["content"].lower()
    assert not payload["content"].strip().startswith("{")
    assert "batch_id=" not in payload["content"]
    assert validate_chunk_metadata(payload["metadata"])
    assert payload["metadata"]["chunk_type"] == "batch_summary"
    assert "freshness_timestamp" in payload["metadata"]

    recommendation_payload = build_recommendation_chunk(
        recommendation=recommendation,
        batch=batch,
        product=batch.product,
        cooperative_id=batch.cooperative_id,
    )
    assert "Suggested action" in recommendation_payload["content"]
    assert recommendation_payload["metadata"]["chunk_type"] == "recommendation_context"
    assert validate_chunk_metadata(recommendation_payload["metadata"])


def test_parcel_and_preharvest_chunks_are_semantic(db_session):
    cooperative, member, parcel, step = _seed_member_parcel_and_steps(db_session)
    parcel_payload = build_parcel_chunk(
        parcel=parcel,
        member=member,
        recent_preharvest_steps=[step],
        cooperative_id=cooperative.id,
    )
    assert "Parcel" in parcel_payload["content"]
    assert "pre-harvest" in parcel_payload["content"].lower()
    assert parcel_payload["metadata"]["chunk_type"] == "parcel_context"
    assert validate_chunk_metadata(parcel_payload["metadata"])

    step_payload = build_pre_harvest_chunk(
        step=step,
        parcel=parcel,
        member=member,
        cooperative_id=cooperative.id,
    )
    assert "Pre-harvest step" in step_payload["content"]
    assert step_payload["metadata"]["chunk_type"] == "pre_harvest_context"
    assert validate_chunk_metadata(step_payload["metadata"])


def test_ml_prediction_and_anomaly_chunks_include_context(db_session):
    manager = db_session.query(User).first()
    cooperative = manager.cooperative
    batch = cooperative.batches[0]
    prediction = MLPredictionLog(
        batch_id=batch.id,
        model_version="v2.1",
        product="mango",
        critical_stage="Séchage",
        predicted_loss_pct=14.2,
        expected_efficiency_pct=85.8,
        risk_level=RiskLevel.HIGH,
        anomaly_score=0.81,
        is_anomalous=True,
        input_snapshot={"signal": "drying_trend_up"},
        output_snapshot={"confidence": 0.78},
    )
    recommendation_log = MLRecommendationLog(
        batch_id=batch.id,
        structured_recommendation={"action": "Inspect humidity and airflow", "risk_level": "HIGH"},
        llm_explanation="Historical drying variance is high for this product.",
    )
    db_session.add_all([prediction, recommendation_log])
    db_session.flush()
    feedback = RecommendationFeedbackLog(
        recommendation_log_id=recommendation_log.id,
        batch_id=batch.id,
        stage="Séchage",
        context_snapshot={"trend": "up"},
        recommendation_snapshot={"action": "Inspect humidity"},
        accepted=True,
        executed=True,
        delta_loss=-2.4,
        comment="Loss reduced after airflow adjustment",
        model_version="v2.1",
    )
    db_session.add(feedback)
    db_session.commit()

    pred_payload = build_ml_prediction_chunk(prediction=prediction, batch=batch, cooperative_id=cooperative.id)
    assert "ML system predicted" in pred_payload["content"]
    assert pred_payload["metadata"]["chunk_type"] == "ml_prediction_context"
    assert validate_chunk_metadata(pred_payload["metadata"])

    anomaly_payload = build_anomaly_summary_chunk(
        feedback=feedback,
        prediction=prediction,
        recommendation_log=recommendation_log,
        cooperative_id=cooperative.id,
    )
    assert "anomaly" in anomaly_payload["content"].lower()
    assert anomaly_payload["metadata"]["chunk_type"] == "anomaly_summary"
    assert validate_chunk_metadata(anomaly_payload["metadata"])


def test_new_operational_chunk_types_are_semantic_and_valid(db_session):
    manager = db_session.query(User).first()
    cooperative = manager.cooperative
    batch = cooperative.batches[0]
    product = batch.product
    steps = db_session.query(ProcessStep).filter(ProcessStep.batch_id == batch.id).all()
    step = steps[0]

    recommendation = Recommendation(
        batch_id=batch.id,
        loss_pct=11.2,
        efficiency_pct=88.8,
        anomaly_score=0.61,
        risk_level=RiskLevel.MEDIUM,
        suggested_action="Review drying humidity controls",
        rationale="Loss trend is above product-stage baseline",
    )
    db_session.add(recommendation)
    prediction = MLPredictionLog(
        batch_id=batch.id,
        model_version="v5.0",
        product=product.name,
        critical_stage="drying",
        predicted_loss_pct=10.9,
        expected_efficiency_pct=89.1,
        risk_level=RiskLevel.MEDIUM,
        anomaly_score=0.59,
        is_anomalous=False,
        input_snapshot={"trend": "stable"},
        output_snapshot={"confidence": 0.72},
    )
    db_session.add(prediction)
    db_session.commit()

    product_stage_payload = build_product_stage_summary_chunk(
        step=step,
        batch=batch,
        product=product,
        cooperative_id=cooperative.id,
        product_stage_avg_loss_pct=5.0,
        cooperative_stage_avg_loss_pct=7.0,
    )
    assert product_stage_payload["metadata"]["chunk_type"] == "product_stage_summary"
    assert "product" in product_stage_payload["content"].lower()
    assert validate_chunk_metadata(product_stage_payload["metadata"])

    lot_status_payload = build_lot_status_summary_chunk(
        batch=batch,
        product=product,
        process_steps=steps,
        recommendation=recommendation,
        cooperative_id=cooperative.id,
    )
    assert lot_status_payload["metadata"]["chunk_type"] == "lot_status_summary"
    assert "cumulative loss" in lot_status_payload["content"].lower()
    assert validate_chunk_metadata(lot_status_payload["metadata"])

    lot_reco_payload = build_lot_recommendation_summary_chunk(
        recommendation=recommendation,
        batch=batch,
        product=product,
        cooperative_id=cooperative.id,
    )
    assert lot_reco_payload["metadata"]["chunk_type"] == "lot_recommendation_summary"
    assert "lot-specific recommendation" in lot_reco_payload["content"].lower()
    assert validate_chunk_metadata(lot_reco_payload["metadata"])

    risk_payload = build_operational_risk_summary_chunk(
        batch=batch,
        product=product,
        process_steps=steps,
        recommendation=recommendation,
        prediction=prediction,
        cooperative_id=cooperative.id,
    )
    assert risk_payload["metadata"]["chunk_type"] == "operational_risk_summary"
    assert "operational risk summary" in risk_payload["content"].lower()
    assert validate_chunk_metadata(risk_payload["metadata"])

    scoped_payload = build_scoped_loss_summary_chunk(
        source_row_id=f"{step.id}:scoped",
        cooperative_id=cooperative.id,
        product_name=product.name,
        stage=step.type,
        stage_canonical="drying",
        product_stage_loss_pct=5.0,
        cooperative_loss_pct=18.0,
        unrelated_product_name="bissap",
        unrelated_product_loss_pct=42.0,
    )
    assert scoped_payload["metadata"]["chunk_type"] == "scoped_loss_summary"
    assert "do not treat this as direct" in scoped_payload["content"].lower()
    assert validate_chunk_metadata(scoped_payload["metadata"])


def test_commercial_builder_inputs_can_be_created_for_semantics(db_session):
    manager = db_session.query(User).first()
    cooperative = manager.cooperative
    source_product = cooperative.products[0]
    catalog = CommercialCatalogProduct(
        cooperative_id=cooperative.id,
        source_product_id=source_product.id,
        name="Mango premium",
        category="fruit",
        sale_unit="kg",
        sale_price_fcfa=1200.0,
        cost_price_fcfa=800.0,
        total_stock_kg=400.0,
        reserved_stock_kg=30.0,
    )
    db_session.add(catalog)
    db_session.flush()
    order = CommercialOrder(
        cooperative_id=cooperative.id,
        order_number="ORD-SEM-001",
        customer_name="Client Semantic",
        status=CommercialOrderStatus.PREPARING,
        subtotal_fcfa=360000.0,
        tax_rate=0.18,
        tax_amount_fcfa=64800.0,
        total_amount_fcfa=424800.0,
        source="consumer_app",
    )
    db_session.add(order)
    db_session.flush()
    line = CommercialOrderLine(
        order_id=order.id,
        catalog_product_id=catalog.id,
        product_name_snapshot=catalog.name,
        unit_snapshot="kg",
        quantity=300.0,
        quantity_kg=300.0,
        unit_price_fcfa=1200.0,
        line_total_fcfa=360000.0,
    )
    db_session.add(line)
    db_session.flush()

    member = _seed_member_parcel_and_steps(db_session)[1]
    charge = GlobalCharge(
        cooperative_id=cooperative.id,
        member_id=member.id,
        parcel_id=None,
        pre_harvest_step_id=None,
        batch_id=cooperative.batches[0].id,
        process_step_id=None,
        charge_type="transport",
        label="Transport lot",
        amount_fcfa=25000.0,
        date=date.today(),
        notes="Truck rental",
        source_type="manual",
    )
    db_session.add(charge)
    db_session.commit()

    order_payload = build_commercial_order_chunk(order=order, cooperative_id=cooperative.id)
    assert "Commercial order" in order_payload["content"]
    assert order_payload["metadata"]["chunk_type"] == "commercial_context"
    assert validate_chunk_metadata(order_payload["metadata"])

    charge_payload = build_global_charge_chunk(
        charge=charge,
        member=member,
        parcel=None,
        step=None,
        cooperative_id=cooperative.id,
    )
    assert "Global charge" in charge_payload["content"]
    assert charge_payload["metadata"]["source_table"] == "global_charges"
    assert validate_chunk_metadata(charge_payload["metadata"])
