from pathlib import Path
import sys

from app.core.config import settings
from app.schemas.chat import ChatRequest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from ai.rag.embeddings import EmbeddingService  # noqa: E402
from ai.rag.vector_store import PGVectorStore  # noqa: E402
from ai.rag.retriever import Retriever  # noqa: E402
from ai.rag.pipeline import RAGPipeline  # noqa: E402


def run_chat(payload: ChatRequest) -> dict:
    if not settings.openai_api_key:
        return {
            "answer": "OPENAI_API_KEY is missing. Configure backend/.env to enable /api/chat.",
            "sources": [],
        }

    prompt_path = ROOT_DIR / "ai" / "prompts" / "system_prompt.txt"
    system_prompt = prompt_path.read_text(encoding="utf-8")

    embedding_service = EmbeddingService(
        api_key=settings.openai_api_key,
        model=settings.openai_embed_model,
    )
    vector_store = PGVectorStore(settings.database_url.replace("postgresql+psycopg", "postgresql"))
    retriever = Retriever(embedding_service, vector_store)
    pipeline = RAGPipeline(
        retriever=retriever,
        api_key=settings.openai_api_key,
        model=settings.openai_chat_model,
    )

    return pipeline.answer(question=payload.question, system_prompt=system_prompt)
