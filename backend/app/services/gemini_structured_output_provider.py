"""
ContractIQ — Gemini Structured Output Provider (Phase 6A)

Concrete implementation of StructuredLLMProvider using the official Google GenAI SDK (google-genai).
Enforces structured outputs via Gemini JSON mode and strict Pydantic schema validation.

Guarantees:
  - Generates JSON conforming to target Pydantic schema using Gemini response_schema.
  - Strict Pydantic model validation on model response text.
  - Defensive stripping of markdown fences if returned.
  - Zero leakage of raw contract text, prompts, or API keys in logs and exceptions.
  - Testable via dependency injection (mocked genai.Client).
"""

import logging
from typing import Any, Type, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.config import settings
from app.services.structured_output_provider import StructuredLLMProvider
from app.services.structured_output_validator import (
    StructuredOutputConfigurationError,
    StructuredOutputProviderError,
    StructuredOutputValidationError,
    validate_structured_output,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GeminiStructuredOutputProvider(StructuredLLMProvider):
    """
    Google Gemini implementation of StructuredLLMProvider using google-genai SDK.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
        client: genai.Client | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.gemini_api_key
        self._model_name = model_name or settings.llm_model or "gemini-3.8-flash"
        self._temperature = (
            temperature if temperature is not None else settings.llm_temperature
        )

        if client is not None:
            self._client = client
        else:
            if not self._api_key or not self._api_key.strip():
                raise StructuredOutputConfigurationError(
                    "Gemini API key is not configured. Set GEMINI_API_KEY environment variable."
                )
            self._client = genai.Client(api_key=self._api_key.strip())

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def temperature(self) -> float:
        return self._temperature

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_instruction: str | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> T:
        """
        Generates and strictly validates a structured response conforming to schema T.
        """
        if not isinstance(prompt, str) or not prompt.strip():
            raise StructuredOutputValidationError("Prompt must be a non-empty string.")

        if not isinstance(schema, type) or not issubclass(schema, BaseModel):
            raise StructuredOutputValidationError(
                f"Schema must be a Pydantic BaseModel subclass, got {schema!r}."
            )

        eff_temp = temperature if temperature is not None else self._temperature

        # Build GenerateContentConfig
        config_args: dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_schema": schema,
            "temperature": eff_temp,
        }
        if system_instruction is not None:
            config_args["system_instruction"] = system_instruction

        # Merge any caller-provided config options
        for k, v in kwargs.items():
            if k not in config_args and v is not None:
                config_args[k] = v

        config = types.GenerateContentConfig(**config_args)

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            logger.error(
                "Gemini API structured call failed for model '%s': %s",
                self._model_name,
                type(exc).__name__,
            )
            raise StructuredOutputProviderError(
                f"Gemini API structured generation failed ({type(exc).__name__}): {str(exc)}"
            ) from exc

        # Extract text safely from response
        raw_text: str | None = None
        try:
            raw_text = response.text if response is not None else None
        except Exception as exc:
            raise StructuredOutputProviderError(
                f"Failed to read text from Gemini response: {str(exc)}"
            ) from exc

        if not raw_text or not raw_text.strip():
            raise StructuredOutputProviderError(
                "Gemini returned an empty response or content was blocked."
            )

        # Validate strictly against Pydantic schema
        return validate_structured_output(raw_text=raw_text, schema=schema)
