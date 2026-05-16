from openai import OpenAI
from ai.rag.retriever import Retriever


class RAGPipeline:
    def __init__(self, retriever: Retriever, api_key: str, model: str = "gpt-4.1-mini"):
        self.retriever = retriever
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def answer(self, question: str, system_prompt: str) -> dict:
        docs = self.retriever.retrieve(question=question, k=5)
        context = "\n\n".join([f"[{d['source']}] {d['content']}" for d in docs])

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nRetrieved context:\n{context}",
                },
            ],
        )

        return {
            "answer": response.choices[0].message.content,
            "sources": [{"source": d["source"], "score": d["score"]} for d in docs],
        }
