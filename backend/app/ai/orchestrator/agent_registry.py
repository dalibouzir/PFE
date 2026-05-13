from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.agents.memory_agent import MemoryAgent
from app.ai.agents.ml_loss_agent import MLLossAgent
from app.ai.agents.out_of_scope_agent import OutOfScopeAgent
from app.ai.agents.rag_knowledge_agent import RAGKnowledgeAgent
from app.ai.agents.recommendation_agent import RecommendationAgent
from app.ai.agents.smalltalk_agent import SmallTalkAgent
from app.ai.agents.sql_analytics_agent import SQLAnalyticsAgent
from app.ai.schemas.agent_schemas import AgentRoute
from app.ai.tools.ml_tools import MLTools
from app.ai.tools.rag_tools import RAGTools
from app.ai.tools.recommendation_tools import RecommendationTools
from app.ai.tools.sql_tools import SQLTools
from app.models.user import User


class AgentRegistry:
    """Lightweight route-to-agent mapping for controlled tool execution."""

    def __init__(self, db: Session, current_user: User):
        sql_tools = SQLTools(db, current_user)
        rag_tools = RAGTools(db, current_user)
        ml_tools = MLTools(db, current_user)
        recommendation_tools = RecommendationTools(db, current_user)

        self._agents = {
            "SQLAnalyticsAgent": SQLAnalyticsAgent(sql_tools),
            "RAGKnowledgeAgent": RAGKnowledgeAgent(rag_tools),
            "MLLossAgent": MLLossAgent(ml_tools),
            "RecommendationAgent": RecommendationAgent(recommendation_tools),
            "SmallTalkAgent": SmallTalkAgent(),
            "OutOfScopeAgent": OutOfScopeAgent(),
            "MemoryAgent": MemoryAgent(db, current_user),
        }

        self._route_map = {
            AgentRoute.SQL_ONLY: ["SQLAnalyticsAgent"],
            AgentRoute.RAG_ONLY: ["RAGKnowledgeAgent"],
            AgentRoute.ML_ONLY: ["MLLossAgent"],
            AgentRoute.RECOMMENDATION_ONLY: ["RecommendationAgent"],
            AgentRoute.HYBRID_SQL_RAG: ["SQLAnalyticsAgent", "RAGKnowledgeAgent"],
            AgentRoute.HYBRID_SQL_ML: ["SQLAnalyticsAgent", "MLLossAgent"],
            AgentRoute.HYBRID_RAG_RECOMMENDATION: ["RAGKnowledgeAgent", "RecommendationAgent"],
            AgentRoute.HYBRID_FULL: ["SQLAnalyticsAgent", "MLLossAgent", "RAGKnowledgeAgent", "RecommendationAgent"],
            AgentRoute.SMALL_TALK: ["SmallTalkAgent"],
            AgentRoute.OUT_OF_SCOPE: ["OutOfScopeAgent"],
        }

    def agents_for_route(self, route: AgentRoute):
        return [self._agents[name] for name in self._route_map.get(route, []) if name in self._agents]

    def required_agent_names(self, route: AgentRoute) -> list[str]:
        return list(self._route_map.get(route, []))

    @property
    def memory_agent(self) -> MemoryAgent:
        return self._agents["MemoryAgent"]
