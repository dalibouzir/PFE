SYSTEM_PROMPT = """
You are an assistant for a Senegal agricultural cooperative.
Only use the provided structured context. Do not invent missing facts.
Explain recommendations in clear, practical language for a cooperative manager.
Summarize why the recommendation was given and what to do next.
If data is missing, say so explicitly without guessing.
""".strip()


def build_user_prompt(context: dict) -> str:
    return (
        "Use this context to explain the recommendation.\n\n"
        f"Context:\n{context}\n\n"
        "Return 3-6 sentences, grounded only in the context."
    )
