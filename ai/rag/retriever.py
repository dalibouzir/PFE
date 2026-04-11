from ai.rag.embeddings import EmbeddingService
from ai.rag.vector_store import PGVectorStore


class Retriever:
    def __init__(self, embedding_service: EmbeddingService, vector_store: PGVectorStore):
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def retrieve(self, question: str, k: int = 5) -> list[dict]:
        query_embedding = self.embedding_service.embed_text(question)
        return self.vector_store.similarity_search(query_embedding, k=k)
