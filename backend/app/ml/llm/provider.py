from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx

from app.core.config import settings
from app.ml.llm.prompt import SYSTEM_PROMPT, build_user_prompt
from app.utils.exceptions import ValidationError

import logging

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str


class LLMClient:
    def __init__(self, api_key: str, base_url: str, model: str, provider_name: str = "unknown"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.provider_name = provider_name

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
            logger.error(f"{self.provider_name} LLM request timed out.")
            raise ValidationError("LLM request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            error_msg = f"{self.provider_name} returned HTTP {status}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from exc
        except httpx.RequestError as exc:
            logger.error(f"{self.provider_name} LLM request failed: {exc}")
            raise ValidationError("LLM request failed.") from exc

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            raise ValidationError("LLM response was empty.")
        return LLMResponse(content=content.strip())


def _create_openrouter_client() -> Optional[LLMClient]:
    """Create OpenRouter client if credentials are available."""
    if not settings.openrouter_api_key:
        return None
    return LLMClient(
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1/chat/completions",
        model=settings.llm_model,
        provider_name="OpenRouter",
    )


def _create_groq_client() -> Optional[LLMClient]:
    """Create Groq client if credentials are available."""
    if not settings.groq_api_key:
        return None
    return LLMClient(
        api_key=settings.groq_api_key,
        base_url="https://api.groq.com/openai/v1/chat/completions",
        model=settings.groq_model,
        provider_name="Groq",
    )


def get_llm_client() -> LLMClient:
    """Get LLM client with credentials-based provider selection.
    
    Returns available client based on configuration priority:
    1. If LLM_PROVIDER=openrouter and credentials present: OpenRouter
    2. If LLM_PROVIDER=groq and credentials present: Groq
    3. Fallback to any available: Try Groq first (more reliable), then OpenRouter
    """
    primary_provider = settings.llm_provider.lower().strip()
    
    # If primary is openrouter, try it first
    if primary_provider == "openrouter":
        if settings.openrouter_api_key:
            return _create_openrouter_client()
        # Fall back to Groq
        if settings.groq_api_key:
            logger.warning("OpenRouter credentials missing or invalid, using Groq")
            return _create_groq_client()
    
    # If primary is groq or anything else, try groq first (more stable)
    elif primary_provider == "groq":
        if settings.groq_api_key:
            return _create_groq_client()
        # Fall back to OpenRouter
        if settings.openrouter_api_key:
            logger.warning("Groq credentials missing or invalid, using OpenRouter")
            return _create_openrouter_client()
    
    # If no primary provider specified, try Groq first, then OpenRouter
    else:
        if settings.groq_api_key:
            logger.warning(f"Invalid LLM_PROVIDER '{primary_provider}', using Groq")
            return _create_groq_client()
        if settings.openrouter_api_key:
            logger.warning(f"Invalid LLM_PROVIDER '{primary_provider}', using OpenRouter")
            return _create_openrouter_client()
    
    raise ValidationError("No LLM provider credentials found. Configure OPENROUTER_API_KEY or GROQ_API_KEY.")


def generate_explanation(context: Dict) -> str:
    client = get_llm_client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(context)},
    ]
    response = client.chat(messages)
    return response.content
