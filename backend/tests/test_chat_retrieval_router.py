from app.services.chat_retrieval_router import RetrievalIntentType, build_retrieval_plan


def test_router_classifies_current_stock_as_sql_only():
    plan = build_retrieval_plan("current stock of mango")
    assert plan.intent_type == RetrievalIntentType.SQL_ONLY.value
    assert plan.sql_needed is True
    assert plan.rag_needed is False


def test_router_classifies_active_lots_as_sql_only():
    plan = build_retrieval_plan("how many active lots?")
    assert plan.intent_type == RetrievalIntentType.SQL_ONLY.value
    assert "batches" in plan.suggested_sql_domains


def test_router_classifies_unpaid_invoices_as_sql_only():
    plan = build_retrieval_plan("unpaid invoices")
    assert plan.intent_type == RetrievalIntentType.SQL_ONLY.value
    assert "commercial_invoices" in plan.suggested_sql_domains


def test_router_classifies_available_quantity_prompt_as_sql_only():
    plan = build_retrieval_plan("donne la quantite disponible de banane")
    assert plan.intent_type == RetrievalIntentType.SQL_ONLY.value


def test_router_classifies_member_directory_list_as_sql_only():
    plan = build_retrieval_plan("liste les membres actifs avec code et statut")
    assert plan.intent_type == RetrievalIntentType.SQL_ONLY.value
    assert plan.rag_needed is False
    assert "members" in plan.suggested_sql_domains


def test_router_classifies_lot_table_request_as_sql_only():
    plan = build_retrieval_plan("affiche un tableau des lots actifs avec quantité entrée et sortie")
    assert plan.intent_type == RetrievalIntentType.SQL_ONLY.value
    assert plan.rag_needed is False
    assert "batches" in plan.suggested_sql_domains


def test_router_classifies_best_practices_as_rag_only():
    plan = build_retrieval_plan("best practices for drying mango")
    assert plan.intent_type == RetrievalIntentType.RAG_ONLY.value
    assert plan.sql_needed is False
    assert plan.rag_needed is True


def test_router_classifies_benchmark_question_as_rag_only():
    plan = build_retrieval_plan("what does benchmark say about millet losses")
    assert plan.intent_type == RetrievalIntentType.RAG_ONLY.value
    assert "benchmark_reference" in plan.suggested_rag_chunk_types
    assert "agronomic_knowledge" in plan.suggested_rag_chunk_types


def test_router_classifies_why_losses_increased_as_hybrid():
    plan = build_retrieval_plan("why did drying losses increase this week")
    assert plan.intent_type == RetrievalIntentType.HYBRID.value
    assert plan.sql_needed is True
    assert plan.rag_needed is True


def test_router_classifies_risky_lot_with_action_as_hybrid():
    plan = build_retrieval_plan("which lot is most risky and what should we do")
    assert plan.intent_type == RetrievalIntentType.HYBRID.value
    assert "batches" in plan.suggested_sql_domains
    assert "anomaly_context" in plan.suggested_rag_chunk_types


def test_router_classifies_unrelated_question_as_unsupported():
    plan = build_retrieval_plan("who won the last football world cup")
    assert plan.intent_type == RetrievalIntentType.UNSUPPORTED.value
    assert plan.sql_needed is False
    assert plan.rag_needed is False


def test_router_detects_product_entities():
    plan = build_retrieval_plan("current stock of Mangue and millet")
    assert "mangue" in plan.detected_entities["products"]
    assert "millet" in plan.detected_entities["products"]


def test_router_detects_stage_entities():
    plan = build_retrieval_plan("explain sorting and Sechage losses")
    assert "sorting" in plan.detected_entities["stages"]
    assert "sechage" in plan.detected_entities["stages"]


def test_router_detects_time_hints():
    plan = build_retrieval_plan("why are losses high this week")
    assert "this week" in plan.detected_entities["time_hints"]


def test_router_detects_batch_code():
    plan = build_retrieval_plan("latest step of LOT-MANG-003")
    assert "LOT-MANG-003" in plan.detected_entities["batch_codes"]


def test_router_classifies_hello_as_small_talk():
    plan = build_retrieval_plan("hello")
    assert plan.intent_type == RetrievalIntentType.SMALL_TALK.value
    assert plan.sql_needed is False
    assert plan.rag_needed is False


def test_router_classifies_vague_short_prompt_as_clarification_needed():
    plan = build_retrieval_plan("analyse")
    assert plan.intent_type == RetrievalIntentType.CLARIFICATION_NEEDED.value
    assert plan.sql_needed is False
    assert plan.rag_needed is False


def test_router_does_not_allow_hybrid_for_greetings():
    plan = build_retrieval_plan("bonjour")
    assert plan.intent_type == RetrievalIntentType.SMALL_TALK.value


def test_router_routes_post_harvest_storage_guidance_to_rag_only():
    plan = build_retrieval_plan("Quels conseils post-récolte pour le stockage afin de réduire les pertes ?")
    assert plan.intent_type == RetrievalIntentType.RAG_ONLY.value
    assert plan.sql_needed is False
    assert plan.rag_needed is True


def test_router_routes_packaging_conservation_guidance_to_rag_only():
    plan = build_retrieval_plan("Quelles recommandations d'emballage améliorent la conservation ?")
    assert plan.intent_type == RetrievalIntentType.RAG_ONLY.value
    assert plan.sql_needed is False
    assert plan.rag_needed is True


def test_router_routes_lot_comparison_with_explanation_to_hybrid():
    plan = build_retrieval_plan("Compare la performance des lots LOT-MANG-001 et LOT-BISS-001 et explique les écarts.")
    assert plan.intent_type == RetrievalIntentType.HYBRID.value
    assert plan.sql_needed is True
    assert plan.rag_needed is True


def test_router_routes_mass_balance_with_risks_to_hybrid():
    plan = build_retrieval_plan("Fais un bilan matière du lot LOT-MANG-001 avec les risques associés.")
    assert plan.intent_type == RetrievalIntentType.HYBRID.value
    assert plan.sql_needed is True
    assert plan.rag_needed is True


def test_router_routes_operational_risks_today_to_hybrid():
    plan = build_retrieval_plan("Quels sont les risques critiques opérationnels de la coopérative aujourd'hui ?")
    assert plan.intent_type == RetrievalIntentType.HYBRID.value
    assert plan.sql_needed is True
    assert plan.rag_needed is True


def test_router_routes_benchmarks_plural_to_rag_only():
    plan = build_retrieval_plan("Quels benchmarks de pertes existent pour le mil ?")
    assert plan.intent_type == RetrievalIntentType.RAG_ONLY.value
    assert plan.sql_needed is False
    assert plan.rag_needed is True


def test_router_routes_reference_question_without_known_entity_to_rag_only():
    plan = build_retrieval_plan("Quelles références agronomiques pour la culture CROP_FAKE_8003 ?")
    assert plan.intent_type == RetrievalIntentType.RAG_ONLY.value
