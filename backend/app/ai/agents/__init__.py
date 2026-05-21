from app.ai.agents.base_agent import BaseAgent
try:
    from app.ai.agents.memory_agent import MemoryAgent
except Exception:  # pragma: no cover - protects package import from circular init
    MemoryAgent = None
try:
    from app.ai.agents.ml_loss_agent import MLLossAgent
except Exception:  # pragma: no cover
    MLLossAgent = None
try:
    from app.ai.agents.out_of_scope_agent import OutOfScopeAgent
except Exception:  # pragma: no cover
    OutOfScopeAgent = None
try:
    from app.ai.agents.rag_knowledge_agent import RAGKnowledgeAgent
except Exception:  # pragma: no cover
    RAGKnowledgeAgent = None
try:
    from app.ai.agents.recommendation_agent import RecommendationAgent
except Exception:  # pragma: no cover
    RecommendationAgent = None
try:
    from app.ai.agents.smalltalk_agent import SmallTalkAgent
except Exception:  # pragma: no cover
    SmallTalkAgent = None
try:
    from app.ai.agents.sql_analytics_agent import SQLAnalyticsAgent
except Exception:  # pragma: no cover
    SQLAnalyticsAgent = None

__all__ = [
    "BaseAgent",
    "MemoryAgent",
    "MLLossAgent",
    "OutOfScopeAgent",
    "RAGKnowledgeAgent",
    "RecommendationAgent",
    "SmallTalkAgent",
    "SQLAnalyticsAgent",
]
