from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import httpx

from app.core.config import settings
from app.ml.llm.prompt import SYSTEM_PROMPT, build_user_prompt
from app.utils.exceptions import ValidationError


@dataclass
class LLMResponse:
    content: str


class LLMClient:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def chat(self, messages: List[Dict[str, str]]) -> LLMResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if "openrouter.ai" in self.base_url:
            headers["HTTP-Referer"] = "https://weefarm.local"
            headers["X-Title"] = "WeeFarm ML Assistant"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": settings.llm_max_tokens,
        }

        try:
            with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
                response = client.post(self.base_url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise ValidationError("LLM request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise ValidationError(f"LLM provider returned HTTP {status}.") from exc
        except httpx.RequestError as exc:
            raise ValidationError("LLM request failed.") from exc

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            raise ValidationError("LLM response was empty.")
        return LLMResponse(content=content.strip())


def get_llm_client() -> LLMClient:
    provider = settings.llm_provider.lower()
    if provider == "openrouter":
        if not settings.openrouter_api_key:
            raise ValidationError("OPENROUTER_API_KEY is missing.")
        return LLMClient(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1/chat/completions",
            model=settings.llm_model,
        )
    if provider == "groq":
        if not settings.groq_api_key:
            raise ValidationError("GROQ_API_KEY is missing.")
        return LLMClient(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1/chat/completions",
            model=settings.llm_model,
        )
    raise ValidationError("Unsupported LLM provider.")


def generate_explanation(context: Dict) -> str:
    client = get_llm_client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(context)},
    ]
    response = client.chat(messages)
    return response.content
