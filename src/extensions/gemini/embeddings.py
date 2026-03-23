from __future__ import annotations

import asyncio
import random
from functools import lru_cache

from google import genai
from google.genai import types

from src.config import get_settings
from src.extensions.gemini.gemini import GeminiIntegrationError
from src.logger import get_logger

logger = get_logger("integrations.gemini_embeddings")


class GeminiEmbeddingsService:
    """Thin batched embeddings wrapper for semantic dedupe."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        output_dimensionality: int | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.output_dimensionality = output_dimensionality
        settings = get_settings()
        self.request_timeout_seconds = float(settings.gemini_request_timeout_seconds)
        self.max_retries = settings.gemini_max_retries

    async def embed_texts(
        self,
        *,
        texts: list[str],
        task_type: str = "SEMANTIC_SIMILARITY",
    ) -> list[list[float]]:
        """Embed the provided texts in one batched provider call."""
        sanitized_texts = [text.strip()[:4000] for text in texts if text and text.strip()]
        if not sanitized_texts:
            return []

        response = await self._embed_with_retry(texts=sanitized_texts, task_type=task_type)
        embeddings = getattr(response, "embeddings", None)
        if not isinstance(embeddings, list) or len(embeddings) != len(sanitized_texts):
            raise GeminiIntegrationError("Gemini returned an invalid embeddings payload.")

        return [list(embedding.values) for embedding in embeddings]

    async def _embed_with_retry(self, *, texts: list[str], task_type: str) -> object:
        attempts = self.max_retries + 1
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                async with genai.Client(api_key=self.api_key).aio as client:
                    return await asyncio.wait_for(
                        client.models.embed_content(
                            model=self.model,
                            contents=texts,
                            config=types.EmbedContentConfig(
                                task_type=task_type,
                                output_dimensionality=self.output_dimensionality,
                            ),
                        ),
                        timeout=self.request_timeout_seconds,
                    )
            except Exception as exc:
                last_exc = exc
                if not self._is_retryable_provider_error(exc) or attempt >= attempts:
                    raise
                delay_seconds = min(8.0, (2 ** (attempt - 1)) + random.uniform(0.0, 0.5))
                logger.warning(
                    "gemini_embeddings_retry_scheduled",
                    retry_attempt=attempt,
                    delay_seconds=round(delay_seconds, 2),
                    model=self.model,
                    error=str(exc),
                )
                await asyncio.sleep(delay_seconds)

        raise GeminiIntegrationError(f"Gemini embeddings failed after retries: {last_exc}")

    @staticmethod
    def _is_retryable_provider_error(exc: Exception) -> bool:
        message = str(exc).upper()
        return any(
            marker in message
            for marker in (
                "429",
                "500",
                "503",
                "504",
                "DEADLINE_EXCEEDED",
                "SERVICE UNAVAILABLE",
                "UNAVAILABLE",
                "INTERNAL",
                "TIMEOUT",
            )
        )


@lru_cache(maxsize=1)
def get_gemini_embeddings_service() -> GeminiEmbeddingsService:
    """Build and cache the shared Gemini embeddings service."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise GeminiIntegrationError("Missing required Gemini setting: GEMINI_API_KEY")

    return GeminiEmbeddingsService(
        api_key=settings.gemini_api_key,
        model=settings.gemini_embedding_model,
        output_dimensionality=settings.search_job_embedding_output_dimensionality,
    )
