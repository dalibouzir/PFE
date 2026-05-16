from app.ai.orchestrator.module_registry import ModuleRegistry


def test_detects_operational_module_from_paraphrase():
    registry = ModuleRegistry()
    module = registry.detect_module("donne moi une vue globale de la coopérative")
    assert module in {"cooperative_summary", "members", "stocks", "lots"}


def test_detects_small_talk_and_capability_queries():
    registry = ModuleRegistry()
    assert registry.is_small_talk("salut cava") is True
    assert registry.is_capability_question("tu peux m’aider à faire quoi ?") is True


def test_detects_non_operational_topic():
    registry = ModuleRegistry()
    assert registry.is_non_operational_topic("Quel film me recommandes-tu ?") is True
