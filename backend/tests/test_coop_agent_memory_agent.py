from app.ai.agents.memory_agent import MemoryAgent


def _agent() -> MemoryAgent:
    return MemoryAgent(db=None, current_user=None)  # type: ignore[arg-type]


def test_should_reuse_referential_followup():
    agent = _agent()
    current = {"scope": "global", "module": "global"}
    previous = {"scope": "batch", "module": "post_harvest", "batch_ref": "MANG-004", "stage": ["drying"]}

    assert agent.should_reuse_context(query="Et celui-ci ?", current_entities=current, previous_entities=previous) is True


def test_should_reuse_product_followup_phrase():
    agent = _agent()
    current = {"scope": "global", "module": "global", "product": ["mango"]}
    previous = {"scope": "batch", "module": "post_harvest", "batch_ref": "MANG-004", "stage": ["drying"]}

    assert agent.should_reuse_context(query="pour la mangue ?", current_entities=current, previous_entities=previous) is True


def test_should_not_reuse_for_unrelated_reset_query():
    agent = _agent()
    current = {"scope": "global", "module": "global"}
    previous = {"scope": "batch", "module": "post_harvest", "batch_ref": "MANG-004", "stage": ["drying"]}

    assert agent.should_reuse_context(query="Quelle meteo demain a Tunis ?", current_entities=current, previous_entities=previous) is False


def test_combined_reset_and_ambiguous_lot_query_is_detected():
    agent = _agent()
    assert agent._is_combined_reset_and_ambiguous_lot_query("Oublie ce lot. Et celui-ci, quelle est sa perte ?") is True
    assert agent._is_combined_reset_and_ambiguous_lot_query("Et celui-ci, quelle est sa perte ?") is False


def test_merge_drops_previous_batch_on_product_change():
    agent = _agent()
    current = {"product": ["peanut"]}
    previous = {"batch_ref": "MANG-004", "product": ["mango"], "scope": "batch", "module": "post_harvest"}

    merged = agent.merge_entities(current, previous)

    assert merged.get("product") == ["peanut"]
    assert merged.get("batch_ref") is None
