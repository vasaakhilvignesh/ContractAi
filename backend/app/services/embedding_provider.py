"""
ContractIQ — Embedding Provider Abstraction (Phase 4A)

Defines the contract for text embedding generation used across the platform.
Supports document indexing (RETRIEVAL_DOCUMENT) and future search queries (RETRIEVAL_QUERY).

Core guarantees:
  - N input texts -> N embeddings with identical ordering preserved.
  - Dimension enforcement (768 for gemini-embedding-2).
  - Explicit task types: RETRIEVAL_DOCUMENT and RETRIEVAL_QUERY.
  - No exposure of sensitive contract text or credentials in exceptions/logs.
"""

from abc import ABC, abstractmethod
from enum import Enum


class EmbeddingTaskType(str, Enum):
    """
    Embedding task types supported by ContractIQ.
    Maps to Gemini embedding task types for optimal retrieval performance.
    """
    RETRIEVAL_DOCUMENT = "RETRIEVAL_DOCUMENT"
    RETRIEVAL_QUERY = "RETRIEVAL_QUERY"


class EmbeddingError(Exception):
    """Base exception for all embedding-related errors."""
    pass


class EmbeddingConfigurationError(EmbeddingError):
    """Raised when the provider is misconfigured or missing required credentials."""
    pass


class EmbeddingValidationError(EmbeddingError):
    """Raised when input texts or parameters fail validation."""
    pass


class EmbeddingProviderError(EmbeddingError):
    """Raised when the upstream provider call fails."""
    pass


class EmbeddingProvider(ABC):
    """
    Abstract Base Class for embedding providers.
    All implementations must guarantee N -> N output mapping and preserved ordering.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name/identifier of the underlying embedding model."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Fixed dimensionality of output embedding vectors."""
        pass

    @abstractmethod
    async def embed_texts(
        self,
        texts: list[str],
        task_type: EmbeddingTaskType | str = EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        title: str | None = None,
    ) -> list[list[float]]:
        """
        Calculates embeddings for a list of input texts.

        Args:
            texts: List of text strings to embed.
            task_type: Intended downstream task (RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY).
            title: Optional document title context (primarily for document chunks).

        Returns:
            List of embedding vectors (list of floats) where len(result) == len(texts)
            and result[i] corresponds strictly to texts[i].
        """
        pass

    async def embed_query(self, text: str) -> list[float]:
        """
        Calculates a single embedding for a search or retrieval query.

        Args:
            text: Query string to embed.

        Returns:
            Embedding vector of floats with length == self.dimension.
        """
        if not isinstance(text, str) or not text.strip():
            raise EmbeddingValidationError("Query text must be a non-empty string.")

        results = await self.embed_texts(
            texts=[text],
            task_type=EmbeddingTaskType.RETRIEVAL_QUERY,
        )
        if not results:
            raise EmbeddingProviderError("Provider returned no embedding for query.")
        return results[0]
