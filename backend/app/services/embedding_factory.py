"""
ContractIQ — Embedding Provider Factory (Phase 4A)

Provides a simple, interview-defensible factory function to instantiate
the configured embedding provider (Google Gemini gemini-embedding-2).
"""

from app.core.config import settings
from app.services.embedding_provider import (
    EmbeddingConfigurationError,
    EmbeddingProvider,
)
from app.services.gemini_embedding_provider import GeminiEmbeddingProvider


def get_embedding_provider(
    provider_name: str | None = None,
    api_key: str | None = None,
) -> EmbeddingProvider:
    """
    Instantiates and returns the configured embedding provider.

    Args:
        provider_name: Optional provider name override (defaults to settings.embedding_provider).
        api_key: Optional API key override (defaults to settings.gemini_api_key).

    Returns:
        Configured EmbeddingProvider instance.

    Raises:
        EmbeddingConfigurationError if provider is unknown or misconfigured.
    """
    selected = (provider_name or settings.embedding_provider or "gemini").lower().strip()

    if selected == "gemini":
        return GeminiEmbeddingProvider(
            api_key=api_key,
            model_name=settings.embedding_model,
            dimension=settings.embedding_dimension,
            batch_size=settings.embedding_batch_size,
        )

    raise EmbeddingConfigurationError(
        f"Unsupported embedding provider: '{selected}'. ContractIQ currently supports 'gemini'."
    )
