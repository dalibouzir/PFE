from typing import Any
import psycopg


class PGVectorStore:
    def __init__(self, dsn: str):
        self.dsn = dsn

    def similarity_search(self, query_embedding: list[float], k: int = 5) -> list[dict[str, Any]]:
        sql = """
            SELECT id, source, content, 1 - (embedding <=> %(embedding)s::vector) AS score
            FROM knowledge_chunks
            ORDER BY embedding <=> %(embedding)s::vector
            LIMIT %(k)s;
        """
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"embedding": query_embedding, "k": k})
                rows = cur.fetchall()

        return [
            {
                "id": str(row[0]),
                "source": row[1],
                "content": row[2],
                "score": float(row[3]),
            }
            for row in rows
        ]
