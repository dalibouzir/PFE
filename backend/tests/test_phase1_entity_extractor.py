from app.ai.orchestrator.entity_extractor import EntityExtractor
from app.ai.orchestrator.intent_router import IntentRouter
from app.ai.schemas.agent_schemas import AgentRoute


def test_valid_batch_reference_is_extracted():
    entities = EntityExtractor().extract("Analyse le lot MANG-004").as_dict()

    assert entities["batch_ref"] == "MANG-004"
    assert entities["specific_batch_requested"] is True
    assert entities["scope"] == "batch"


def test_general_risk_question_does_not_extract_fake_batch_reference():
    entities = EntityExtractor().extract("Avons-nous des lots à risque ?").as_dict()

    assert entities["batch_ref"] is None
    assert entities["batch_ref_candidate"] is None
    assert entities["specific_batch_requested"] is False
    assert "risk" in entities["metric"]
    assert entities["scope"] == "post_harvest"


def test_common_french_words_are_not_batch_references():
    extractor = EntityExtractor()

    for query in [
        "Quelle étape cause le plus de pertes ?",
        "Pourquoi les pertes sont élevées ?",
        "Comment réduire les pertes pendant le tri ?",
        "Donne le stock de mangue.",
    ]:
        entities = extractor.extract(query).as_dict()
        assert entities["batch_ref"] is None
        assert entities["batch_ref_candidate"] is None


def test_unknown_valid_looking_reference_is_kept_only_when_specific_lot_requested():
    entities = EntityExtractor().extract("Analyse le lot MANG-999").as_dict()

    assert entities["batch_ref"] == "MANG-999"
    assert entities["specific_batch_requested"] is True


def test_known_database_reference_can_be_resolved_even_with_custom_code():
    entities = EntityExtractor().extract("Analyse le lot PROD-777", known_batch_refs={"PROD-777"}).as_dict()

    assert entities["batch_ref"] == "PROD-777"
    assert entities["specific_batch_requested"] is True


def test_light_fuzzy_batch_reference_matching_with_known_refs():
    entities = EntityExtractor().extract("Analyse le lot MANG-05", known_batch_refs={"MANG-005"}).as_dict()

    assert entities["batch_ref"] == "MANG-005"
    assert entities["specific_batch_requested"] is True


def test_light_fuzzy_product_matching():
    entities = EntityExtractor().extract("Comment réduire les pertes sur mangu au sechage ?").as_dict()

    assert "mango" in entities["product"]
    assert "drying" in entities["stage"]


def test_sitation_typo_is_normalized_for_intent_detection():
    entities = EntityExtractor().extract("Analyse la sitation du lot MANG-004").as_dict()

    assert entities["batch_ref"] == "MANG-004"
    assert entities["scope"] == "batch"


def test_general_risk_question_routes_to_sql_ml_without_fake_reference():
    decision = IntentRouter().classify("Avons-nous des lots à risque ?", known_batch_refs={"MANG-004"})

    assert decision.route == AgentRoute.HYBRID_SQL_ML
    assert decision.detected_entities["batch_ref"] is None
    assert "SQLAnalyticsAgent" in decision.required_agents
    assert "MLLossAgent" in decision.required_agents


def test_stage_loss_causal_question_routes_to_sql_and_rag():
    decision = IntentRouter().classify("Pourquoi le séchage cause beaucoup de pertes ?")

    assert decision.route == AgentRoute.HYBRID_SQL_RAG
    assert decision.required_agents == ["SQLAnalyticsAgent", "RAGKnowledgeAgent"]
    assert decision.detected_entities["stage"] == ["drying"]
