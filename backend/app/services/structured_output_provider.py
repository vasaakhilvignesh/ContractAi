"""
ContractIQ — Structured LLM Provider Interface (Phase 6A)

Defines the vendor-independent contract for generating structured LLM responses.
Decouples business extraction schemas and deterministic rule engines from specific
LLM models and SDK providers.

Core guarantees:
  - Strict Pydantic model response validation.
  - Asynchronous generation API.
  - Zero leakage of secrets or sensitive prompt text in error traces.
  - Clean provider substitution (e.g. Gemini, future OpenAI/Claude/local).
"""

from abc import ABC, abstractmethod
from typing import Any, Type, TypeVar

from pydantic import BaseModel

from app.services.structured_output_validator import (
    StructuredOutputConfigurationError,
    StructuredOutputError,
    StructuredOutputParseError,
    StructuredOutputProviderError,
    StructuredOutputValidationError,
)

T = TypeVar("T", bound=BaseModel)


class StructuredLLMProvider(ABC):
    """
    Abstract Base Class for structured LLM providers.
    All implementations must return strictly validated Pydantic model instances.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name/identifier of the underlying LLM model."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_instruction: str | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> T:
        """
        Generates and strictly validates a structured LLM response matching schema T.

        Args:
            prompt: Main prompt content (e.g. text context, question, instructions).
            schema: Pydantic model class to validate the LLM output against.
            system_instruction: Optional system instruction / persona context.
            temperature: Sampling temperature (default 0.0 for deterministic outputs).
            **kwargs: Additional provider-specific generation parameters.

        Returns:
            An instance of T strictly conforming to the provided schema.

        Raises:
            StructuredOutputConfigurationError: Provider is misconfigured or missing credentials.
            StructuredOutputProviderError: Upstream LLM call failed or returned empty response.
            StructuredOutputParseError: LLM output could not be parsed as valid JSON.
            StructuredOutputValidationError: LLM output parsed as JSON but failed schema validation.
        """
        pass
