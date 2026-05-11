from app.models.user import User
from app.services.rag_context_builders import build_batch_summary_chunk
from app.services.rag_freshness_policy import RefreshMode, get_all_freshness_policies, get_freshness_policy
from app.services.rag_indexer import ReindexCounters
from app.services.rag_reindex_hooks import reindex_batch_if_needed


def test_freshness_policy_exists_for_required_chunk_types():
    policies = get_all_freshness_policies()
    required = {
        "batch_summary",
        "process_step_summary",
        "recommendation_context",
        "anomaly_summary",
        "parcel_context",
        "pre_harvest_context",
        "commercial_context",
        "ml_prediction_context",
        "ml_training_context",
        "benchmark_reference",
        "agronomic_knowledge",
    }
    for chunk_type in required:
        assert chunk_type in policies

    assert get_freshness_policy("batch_summary").refresh_mode == RefreshMode.ON_CREATE_UPDATE
    assert get_freshness_policy("batch_summary").max_age_minutes == 60
    assert get_freshness_policy("anomaly_summary").max_age_minutes == 15
    assert get_freshness_policy("parcel_context").refresh_mode == RefreshMode.SCHEDULED_DAILY
    assert get_freshness_policy("ml_training_context").refresh_mode == RefreshMode.MANUAL_ONLY


def test_freshness_timestamp_present_in_semantic_metadata(db_session):
    manager = db_session.query(User).first()
    batch = manager.cooperative.batches[0]
    steps = batch.process_steps
    payload = build_batch_summary_chunk(
        batch=batch,
        product=batch.product,
        process_steps=steps,
        recommendation=batch.recommendation,
        cooperative_id=batch.cooperative_id,
    )
    metadata = payload["metadata"]
    assert "freshness_timestamp" in metadata
    assert metadata["freshness_timestamp"]


def test_reindex_hook_uses_targeted_reindex_not_full(monkeypatch, db_session):
    manager = db_session.query(User).first()
    batch = manager.cooperative.batches[0]
    called = {}

    def _fake_targeted(*args, **kwargs):
        called["targets"] = kwargs.get("targets")
        return ReindexCounters()

    monkeypatch.setattr("app.services.rag_reindex_hooks.reindex_targeted_sources", _fake_targeted)
    reindex_batch_if_needed(
        db_session,
        current_user=manager,
        batch_id=batch.id,
        cooperative_id=batch.cooperative_id,
    )
    assert called.get("targets")
    assert any(item[0] == "batches" for item in called["targets"])
