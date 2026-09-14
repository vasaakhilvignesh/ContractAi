"""
ContractIQ — Gemini Embedding Provider (Phase 4A)

Concrete implementation of EmbeddingProvider using the official Google GenAI SDK (google-genai).
Uses `gemini-embedding-2` with 768 output dimensions and cosine similarity.

Guarantees:
  - N input texts -> N embeddings with identical ordering preserved.
  - Strict dimension verification (768).
  - Batching support respecting configured batch size.
  - Zero leakage of raw contract text or API keys in logs and exceptions.
  - Supported task types: RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY.
"""

import logging
import time
from typing import Any

from google import genai
from google.genai import types

from app.core.config import settings
from app.core.observability import log_operation_result
from app.services.embedding_provider import (
    EmbeddingConfigurationError,
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingTaskType,
    EmbeddingValidationError,
)

logger = logging.getLogger(__name__)


class GeminiEmbeddingProvider(EmbeddingProvider):
    """
    Google Gemini embedding provider using official google-genai SDK.
    Model: gemini-embedding-2 (768 dimensions).
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        dimension: int | None = None,
        batch_size: int | None = None,
        client: genai.Client | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.gemini_api_key
        self._model_name = model_name or settings.embedding_model or "gemini-embedding-2"
        self._dimension = dimension or settings.embedding_dimension or 768
        self._batch_size = batch_size or settings.embedding_batch_size or 100

        if self._dimension != 768:
            raise EmbeddingConfigurationError(
                f"Invalid embedding dimension: {self._dimension}. ContractIQ requires exactly 768 dimensions."
            )

        if "gemini-embedding-2" not in self._model_name:
            raise EmbeddingConfigurationError(
                f"Invalid embedding model: {self._model_name}. ContractIQ requires gemini-embedding-2."
            )

        if client is not None:
            self._client = client
        else:
            if not self._api_key or not self._api_key.strip():
                raise EmbeddingConfigurationError(
                    "Gemini API key is not configured. Set GEMINI_API_KEY environment variable."
                )
            self._client = genai.Client(api_key=self._api_key.strip())

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def batch_size(self) -> int:
        return self._batch_size

    def _validate_inputs(
        self,
        texts: list[str],
        task_type: EmbeddingTaskType | str,
    ) -> EmbeddingTaskType:
        """Validates input texts and task type. Returns normalized EmbeddingTaskType."""
        if texts is None or not isinstance(texts, list):
            raise EmbeddingValidationError("Input texts must be a list of strings.")

        # Normalize and validate task type
        if isinstance(task_type, EmbeddingTaskType):
            normalized_task = task_type
        elif isinstance(task_type, str):
            try:
                normalized_task = EmbeddingTaskType(task_type.upper())
            except ValueError:
                raise EmbeddingValidationError(
                    f"Unsupported task type '{task_type}'. ContractIQ supports only "
                    f"RETRIEVAL_DOCUMENT and RETRIEVAL_QUERY."
                )
        else:
            raise EmbeddingValidationError(
                f"task_type must be an EmbeddingTaskType or str, got {type(task_type).__name__}."
            )

        for i, text in enumerate(texts):
            if not isinstance(text, str):
                raise EmbeddingValidationError(
                    f"Item at index {i} is not a string (type: {type(text).__name__})."
                )
            if not text.strip():
                raise EmbeddingValidationError(
                    f"Item at index {i} is empty or contains only whitespace."
                )

        return normalized_task

    async def _embed_batch(
        self,
        batch: list[str],
        task_type: EmbeddingTaskType,
        title: str | None = None,
    ) -> list[list[float]]:
        """
        Embeds a single batch of texts using the Gemini API.
        Never logs raw text or sensitive credentials.
        """
        config = types.EmbedContentConfig(
            output_dimensionality=self._dimension,
            task_type=task_type.value,
            title=title if task_type == EmbeddingTaskType.RETRIEVAL_DOCUMENT else None,
        )

        _start = time.perf_counter()
        try:
            response = await self._client.aio.models.embed_content(
                model=self._model_name,
                contents=batch,
                config=config,
            )
        except Exception as e:
            _duration_ms = round((time.perf_counter() - _start) * 1000, 2)
            # Defensive logging without raw text or API key
            logger.error(
                "Gemini embedding API call failed for batch of %d items (model=%s): %s",
                len(batch),
                self._model_name,
                type(e).__name__,
            )
            log_operation_result(
                operation="gemini_embedding_batch",
                duration_ms=_duration_ms,
                status="error",
                metadata={
                    "model": self._model_name,
                    "batch_size": len(batch),
                    "error_type": type(e).__name__,
                },
            )
            raise EmbeddingProviderError(
                f"Gemini embedding request failed: {type(e).__name__}: {str(e)}"
            ) from e

        _duration_ms = round((time.perf_counter() - _start) * 1000, 2)
        log_operation_result(
            operation="gemini_embedding_batch",
            duration_ms=_duration_ms,
            status="ok",
            metadata={
                "model": self._model_name,
                "batch_size": len(batch),
                "embedding_dimension": self._dimension,
            },
        )

        # Validate response structure
        embeddings_raw = getattr(response, "embeddings", None)
        if embeddings_raw is None:
            raise EmbeddingProviderError(
                "Gemini API returned a response with no embeddings field."
            )

        if len(embeddings_raw) != len(batch):
            raise EmbeddingProviderError(
                f"Embedding count mismatch: sent {len(batch)} texts, received {len(embeddings_raw)} embeddings."
            )

        batch_embeddings: list[list[float]] = []
        for idx, emb in enumerate(embeddings_raw):
            values: list[float] | None = None
            if hasattr(emb, "values") and emb.values is not None:
                values = emb.values
            elif isinstance(emb, dict) and "values" in emb:
                values = emb["values"]

            if values is None:
                raise EmbeddingProviderError(
                    f"Embedding at index {idx} contains no vector values."
                )

            if len(values) != self._dimension:
                raise EmbeddingProviderError(
                    f"Embedding dimension mismatch at index {idx}: expected {self._dimension}, "
                    f"received {len(values)}."
                )

            batch_embeddings.append([float(v) for v in values])

        return batch_embeddings

    async def embed_texts(
        self,
        texts: list[str],
        task_type: EmbeddingTaskType | str = EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        title: str | None = None,
    ) -> list[list[float]]:
        """
        Embeds a list of texts, handling batching transparently while preserving N -> N order.

        Args:
            texts: List of text strings to embed.
            task_type: RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY.
            title: Optional title context for document chunks.

        Returns:
            List of 768-dimensional float embedding vectors with identical ordering.
        """
        if texts is None:
            raise EmbeddingValidationError("Input texts cannot be None.")
        if not isinstance(texts, list):
            raise EmbeddingValidationError("Input texts must be a list of strings.")

        if len(texts) == 0:
            return []

        validated_task = self._validate_inputs(texts, task_type)

        all_embeddings: list[list[float]] = []

        # Process in batches to respect API limits and preserve ordering
        for start_idx in range(0, len(texts), self._batch_size):
            batch = texts[start_idx : start_idx + self._batch_size]
            batch_result = await self._embed_batch(
                batch=batch,
                task_type=validated_task,
                title=title,
            )
            all_embeddings.extend(batch_result)

        # Invariant check: N inputs must yield exactly N outputs
        if len(all_embeddings) != len(texts):
            raise EmbeddingProviderError(
                f"Critical ordering error: {len(texts)} inputs yielded {len(all_embeddings)} embeddings."
            )

        return all_embeddings
