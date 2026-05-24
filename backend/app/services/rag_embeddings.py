from __future__ import annotations

import re
import threading
from typing import Iterable, Optional

import httpx
import numpy as np

from app.core.config import settings
from app.utils.exceptions import ValidationError


EMBEDDING_BATCH_SIZE = 64
_LOCAL_MODEL = None
_LOCAL_MODEL_LOCK = threading.Lock()
_LOCAL_ENCODE_LOCK = threading.Lock()


def embed_texts(texts: list[str]) -> list[list[float]]:
    provider = settings.rag_embedding_provider.lower().strip()
    if provider == "local":
        return _local_embeddings(texts)
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValidationError("OPENAI_API_KEY is missing for RAG embeddings.")
        model = _resolve_embedding_model(settings.rag_embedding_model, provider=provider)
        return _request_embeddings(
            base_url="https://api.openai.com/v1/embeddings",
            api_key=settings.openai_api_key,
            model=model,
            texts=texts,
        )
    if provider == "openrouter":
        if not settings.openrouter_api_key:
            raise ValidationError("OPENROUTER_API_KEY is missing for RAG embeddings.")
        model = _resolve_embedding_model(settings.rag_embedding_model, provider=provider)
        return _request_embeddings(
            base_url="https://openrouter.ai/api/v1/embeddings",
            api_key=settings.openrouter_api_key,
            model=model,
            texts=texts,
            extra_headers={
                "HTTP-Referer": "https://weefarm.local",
                "X-Title": "WeeFarm RAG",
            },
        )
    if provider == "custom":
        if not settings.rag_embedding_base_url:
            raise ValidationError("RAG_EMBEDDING_BASE_URL is missing for custom embedding provider.")
        if not settings.rag_embedding_api_key:
            raise ValidationError("RAG_EMBEDDING_API_KEY is missing for custom embedding provider.")
        model = _resolve_embedding_model(settings.rag_embedding_model, provider=provider)
        return _request_embeddings(
            base_url=settings.rag_embedding_base_url.rstrip("/"),
            api_key=settings.rag_embedding_api_key,
            model=model,
            texts=texts,
        )
    raise ValidationError("Unsupported RAG embedding provider.")


def _request_embeddings(
    *,
    base_url: str,
    api_key: str,
    model: str,
    texts: list[str],
    extra_headers: Optional[dict[str, str]] = None,
) -> list[list[float]]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    embeddings: list[list[float]] = []
    try:
        with httpx.Client(timeout=60.0) as client:
            for batch in _batched(texts, EMBEDDING_BATCH_SIZE):
                payload = {
                    "model": model,
                    "input": batch,
                }
                response = client.post(base_url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                rows = data.get("data", [])
                if len(rows) != len(batch):
                    raise ValidationError("Embedding provider returned an unexpected number of vectors.")
                embeddings.extend([row.get("embedding", []) for row in rows])
    except httpx.TimeoutException as exc:
        raise ValidationError("Embedding request timed out.") from exc
    except httpx.HTTPStatusError as exc:
        raise ValidationError(f"Embedding provider returned HTTP {exc.response.status_code}.") from exc
    except httpx.RequestError as exc:
        raise ValidationError("Embedding request failed.") from exc

    for vector in embeddings:
        if len(vector) != settings.rag_embedding_dimensions:
            raise ValidationError(
                f"Embedding dimension mismatch. Expected {settings.rag_embedding_dimensions}, got {len(vector)}."
            )
    return embeddings


def _batched(values: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(values), size):
        yield values[i : i + size]


def _resolve_embedding_model(model: str, *, provider: str) -> str:
    cleaned = model.strip()
    if provider == "openai":
        return re.sub(r"^[^/]+/", "", cleaned)
    return cleaned


def _local_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model_name = settings.rag_embedding_model.strip() or "sentence-transformers/all-MiniLM-L6-v2"
    model = _get_local_model(model_name)
    try:
        with _LOCAL_ENCODE_LOCK:
            vectors = model.encode(
                texts,
                batch_size=min(64, max(1, len(texts))),
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
    except Exception as exc:
        raise ValidationError(f"Local embedding generation failed: {exc}") from exc

    embeddings = np.asarray(vectors, dtype=np.float32).tolist()
    for vector in embeddings:
        if len(vector) != settings.rag_embedding_dimensions:
            raise ValidationError(
                f"Embedding dimension mismatch. Expected {settings.rag_embedding_dimensions}, got {len(vector)}."
            )
    return embeddings


def _get_local_model(model_name: str):
    global _LOCAL_MODEL
    if _LOCAL_MODEL is not None:
        return _LOCAL_MODEL
    with _LOCAL_MODEL_LOCK:
        if _LOCAL_MODEL is not None:
            return _LOCAL_MODEL
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:
            raise ValidationError(
                "Local embeddings require sentence-transformers. Install dependency and retry."
            ) from exc
        _LOCAL_MODEL = SentenceTransformer(model_name)
    return _LOCAL_MODEL
