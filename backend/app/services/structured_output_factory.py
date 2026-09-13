"""
ContractIQ — Structured LLM Provider Factory (Phase 6A)

Factory function for obtaining configured StructuredLLMProvider instances.
Supports dependency injection for unit and integration testing without network calls.
"""

import logging
from typing import Any

from google import genai

from app.core.config import settings
from app.services.gemini_structured_output_provider import GeminiStructuredOutputProvider
from app.services.structured_output_provider import StructuredLLMProvider
from app.services.structured_output_validator import StructuredOutputConfigurationError

logger = logging.getLogger(__name__)


def get_structured_llm_provider(
    provider_type: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
    temperature: float | None = None,
    client: genai.Client | None = None,
) -> StructuredLLMProvider:
    """
    Factory function returning a configured StructuredLLMProvider.

    Args:
        provider_type: Provider identifier ('gemini'). Defaults to settings.llm_provider.
        api_key: Optional API key override.
        model_name: Optional model name override.
        temperature: Optional temperature override.
        client: Optional pre-configured genai.Client for testing.

    Returns:
        StructuredLLMProvider instance.

    Raises:
        StructuredOutputConfigurationError: If the requested provider is unsupported or misconfigured.
    """
    resolved_type = (provider_type or settings.llm_provider or "gemini").strip().lower()

    if resolved_type == "gemini":
        return GeminiStructuredOutputProvider(
            api_key=api_key,
            model_name=model_name,
            temperature=temperature,
            client=client,
        )

    raise StructuredOutputConfigurationError(
        f"Unsupported structured LLM provider '{resolved_type}'. Supported providers: 'gemini'."
    )
