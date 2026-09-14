"""
ContractIQ — Tests for Structured Output Infrastructure (Phase 6A)

Verifies:
  1. Strict Pydantic model validation from raw LLM output.
  2. Markdown code block stripping (```json ... ``` and ``` ... ```).
  3. JSON extraction with surrounding commentary.
  4. Malformed JSON handling with StructuredOutputParseError.
  5. Schema violations (missing fields, wrong types) with StructuredOutputValidationError.
  6. Nested schema validation support.
  7. Provider-independent StructuredLLMProvider interface.
  8. Gemini provider implementation with mocked google-genai SDK.
  9. GenerateContentConfig parameter verification (response_mime_type, response_schema, temperature).
 10. Upstream API errors, empty responses, and blocked content handling.
 11. Missing credentials handling with StructuredOutputConfigurationError.
 12. Factory provider resolution and dependency injection.
 13. Credential hygiene (zero secrets/API keys in error messages).
"""

from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.services.gemini_structured_output_provider import GeminiStructuredOutputProvider
from app.services.structured_output_factory import get_structured_llm_provider
from app.services.structured_output_provider import StructuredLLMProvider
from app.services.structured_output_validator import (
    StructuredOutputConfigurationError,
    StructuredOutputError,
    StructuredOutputParseError,
    StructuredOutputProviderError,
    StructuredOutputValidationError,
    clean_json_text,
    validate_structured_output,
)


# ====================================================================
# Test Pydantic Schemas (Decoupled test-only schemas for Phase 6A)
# ====================================================================

class SimpleTestEntity(BaseModel):
    name: str
    count: int
    is_active: bool = True
    tags: list[str] = Field(default_factory=list)


class ChildItem(BaseModel):
    item_id: str
    value: float


class ComplexTestEntity(BaseModel):
    title: str
    code: str
    items: list[ChildItem]
    metadata: Optional[dict[str, Any]] = None


# ====================================================================
# 1. Validation & Parsing Infrastructure Tests
# ====================================================================

class TestStructuredOutputValidator:
    """Unit tests for the validator and markdown/JSON sanitizer."""

    def test_valid_json_plain(self):
        """Standard valid JSON validates cleanly into the target Pydantic model."""
        raw = '{"name": "Contract A", "count": 10, "is_active": true, "tags": ["saas", "vendor"]}'
        result = validate_structured_output(raw, SimpleTestEntity)

        assert isinstance(result, SimpleTestEntity)
        assert result.name == "Contract A"
        assert result.count == 10
        assert result.is_active is True
        assert result.tags == ["saas", "vendor"]

    def test_valid_json_in_markdown_code_fence(self):
        """JSON wrapped in ```json ... ``` code fences is cleanly extracted and validated."""
        raw = """```json
{
  "name": "Contract B",
  "count": 42,
  "is_active": false,
  "tags": ["procurement"]
}
```"""
        result = validate_structured_output(raw, SimpleTestEntity)
        assert result.name == "Contract B"
        assert result.count == 42
        assert result.is_active is False
        assert result.tags == ["procurement"]

    def test_valid_json_in_generic_markdown_fence(self):
        """JSON wrapped in ``` ... ``` code fences (without 'json' keyword) is parsed cleanly."""
        raw = """```
{"name": "Contract C", "count": 7}
```"""
        result = validate_structured_output(raw, SimpleTestEntity)
        assert result.name == "Contract C"
        assert result.count == 7
        assert result.is_active is True
        assert result.tags == []

    def test_valid_json_with_surrounding_commentary(self):
        """Extracts JSON even if LLM includes preamble and postamble text outside fences."""
        raw = """Here is the structured analysis of the requested document:
```json
{
  "name": "Contract D",
  "count": 99,
  "is_active": true
}
```
I hope this information is helpful for your audit."""
        result = validate_structured_output(raw, SimpleTestEntity)
        assert result.name == "Contract D"
        assert result.count == 99

    def test_valid_json_with_surrounding_commentary_without_fences(self):
        """Extracts JSON between outermost braces when no code fences are present."""
        raw = """Note: Document extraction completed.
{"name": "Contract E", "count": 12}
End of extraction output."""
        result = validate_structured_output(raw, SimpleTestEntity)
        assert result.name == "Contract E"
        assert result.count == 12

    def test_complex_nested_pydantic_schema(self):
        """Validates deeply nested models, lists of models, and optional metadata."""
        raw = """{
  "title": "Master Services Agreement",
  "code": "MSA-2026",
  "items": [
    {"item_id": "clause-1", "value": 1500.50},
    {"item_id": "clause-2", "value": 250.00}
  ],
  "metadata": {"version": 2, "region": "US"}
}"""
        result = validate_structured_output(raw, ComplexTestEntity)
        assert isinstance(result, ComplexTestEntity)
        assert result.title == "Master Services Agreement"
        assert len(result.items) == 2
        assert result.items[0].item_id == "clause-1"
        assert result.items[0].value == 1500.50
        assert result.metadata == {"version": 2, "region": "US"}

    def test_clean_json_text_utility(self):
        """Direct tests for the clean_json_text helper."""
        assert clean_json_text(None) == ""
        assert clean_json_text("   ") == ""
        assert clean_json_text("  {\"a\": 1}  ") == "{\"a\": 1}"
        assert clean_json_text("```json\n{\"a\": 1}\n```") == "{\"a\": 1}"
        assert clean_json_text("```\n{\"a\": 1}\n```") == "{\"a\": 1}"
        assert clean_json_text("```json\n{\"a\": 1}") == "{\"a\": 1}"

    def test_empty_or_whitespace_raises_parse_error(self):
        """Empty or whitespace-only response raises StructuredOutputParseError."""
        with pytest.raises(StructuredOutputParseError) as exc_info:
            validate_structured_output("", SimpleTestEntity)
        assert "empty or whitespace" in str(exc_info.value).lower()
        assert exc_info.value.raw_output == ""

        with pytest.raises(StructuredOutputParseError):
            validate_structured_output("   \n\t  ", SimpleTestEntity)

        with pytest.raises(StructuredOutputParseError):
            validate_structured_output(None, SimpleTestEntity)

    def test_malformed_json_raises_parse_error(self):
        """Invalid JSON syntax raises StructuredOutputParseError with informative error."""
        malformed = '{"name": "Contract A", "count": 10, '  # Unclosed brace
        with pytest.raises(StructuredOutputParseError) as exc_info:
            validate_structured_output(malformed, SimpleTestEntity)

        assert "failed to parse json" in str(exc_info.value).lower()
        assert exc_info.value.raw_output == malformed

    def test_missing_required_field_raises_validation_error(self):
        """Missing required field raises StructuredOutputValidationError with structured error info."""
        missing_name = '{"count": 5}'
        with pytest.raises(StructuredOutputValidationError) as exc_info:
            validate_structured_output(missing_name, SimpleTestEntity)

        err: StructuredOutputValidationError = exc_info.value
        assert "failed schema validation" in str(err).lower()
        assert "name" in str(err)
        assert len(err.validation_errors) > 0
        assert any(e["loc"] == "name" for e in err.validation_errors)
        assert err.raw_output == missing_name

    def test_invalid_type_raises_validation_error(self):
        """Incorrect data type for a field raises StructuredOutputValidationError."""
        bad_type = '{"name": "Contract X", "count": "not_an_integer"}'
        with pytest.raises(StructuredOutputValidationError) as exc_info:
            validate_structured_output(bad_type, SimpleTestEntity)

        err = exc_info.value
        assert "count" in str(err)
        assert any("count" in e["loc"] for e in err.validation_errors)

    def test_invalid_schema_argument_raises_validation_error(self):
        """Passing an invalid non-Pydantic schema type raises StructuredOutputValidationError."""
        with pytest.raises(StructuredOutputValidationError) as exc_info:
            validate_structured_output('{"a": 1}', dict)  # type: ignore[arg-type]
        assert "basemodel subclass" in str(exc_info.value).lower()


# ====================================================================
# 2. Gemini Structured Output Provider Tests (Mocked google-genai)
# ====================================================================

class TestGeminiStructuredOutputProvider:
    """Unit tests verifying GeminiStructuredOutputProvider behavior with mocked SDK."""

    @pytest.mark.asyncio
    async def test_successful_structured_generation(self):
        """Generates and validates structured model output using mocked Gemini client."""
        mock_response = MagicMock()
        mock_response.text = '{"name": "Service Agreement", "count": 3, "is_active": true, "tags": ["legal"]}'

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        provider = GeminiStructuredOutputProvider(
            api_key="mock-gemini-key",
            model_name="gemini-3.8-flash",
            temperature=0.0,
            client=mock_client,
        )

        result = await provider.generate_structured(
            prompt="Extract entity data.",
            schema=SimpleTestEntity,
            system_instruction="You are a strict data extraction system.",
        )

        assert isinstance(result, SimpleTestEntity)
        assert result.name == "Service Agreement"
        assert result.count == 3
        assert result.tags == ["legal"]

        # Verify SDK call details
        mock_client.aio.models.generate_content.assert_awaited_once()
        call_kwargs = mock_client.aio.models.generate_content.await_args.kwargs

        assert call_kwargs["model"] == "gemini-3.8-flash"
        assert call_kwargs["contents"] == "Extract entity data."
        config = call_kwargs["config"]
        assert config.response_mime_type == "application/json"
        assert config.response_schema == SimpleTestEntity
        assert config.temperature == 0.0
        assert config.system_instruction == "You are a strict data extraction system."

    @pytest.mark.asyncio
    async def test_custom_temperature_and_extra_kwargs(self):
        """Custom temperature and extra kwargs are respected during generation."""
        mock_response = MagicMock()
        mock_response.text = '{"name": "Custom Temp", "count": 1}'

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        provider = GeminiStructuredOutputProvider(
            api_key="mock-gemini-key",
            temperature=0.0,
            client=mock_client,
        )

        await provider.generate_structured(
            prompt="Test prompt",
            schema=SimpleTestEntity,
            temperature=0.7,
            max_output_tokens=500,
        )

        call_kwargs = mock_client.aio.models.generate_content.await_args.kwargs
        config = call_kwargs["config"]
        assert config.temperature == 0.7
        assert config.max_output_tokens == 500

    @pytest.mark.asyncio
    async def test_empty_prompt_raises_validation_error(self):
        """Empty or whitespace prompt raises StructuredOutputValidationError."""
        mock_client = MagicMock()
        provider = GeminiStructuredOutputProvider(api_key="mock-key", client=mock_client)

        with pytest.raises(StructuredOutputValidationError) as exc_info:
            await provider.generate_structured(prompt="", schema=SimpleTestEntity)
        assert "prompt must be a non-empty string" in str(exc_info.value).lower()

        with pytest.raises(StructuredOutputValidationError):
            await provider.generate_structured(prompt="   ", schema=SimpleTestEntity)

    def test_missing_api_key_raises_configuration_error(self, monkeypatch):
        """Instantiating provider without an API key raises StructuredOutputConfigurationError."""
        from app.core import config

        # Temporarily clear settings.gemini_api_key
        monkeypatch.setattr(config.settings, "gemini_api_key", "")

        with pytest.raises(StructuredOutputConfigurationError) as exc_info:
            GeminiStructuredOutputProvider(api_key="", client=None)
        assert "api key is not configured" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_upstream_api_exception_wrapped_in_provider_error(self):
        """Exceptions from the Gemini SDK are caught and wrapped in StructuredOutputProviderError."""
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("Network timeout during Gemini call")
        )

        provider = GeminiStructuredOutputProvider(api_key="mock-key", client=mock_client)

        with pytest.raises(StructuredOutputProviderError) as exc_info:
            await provider.generate_structured(prompt="Test", schema=SimpleTestEntity)

        assert "gemini api structured generation failed" in str(exc_info.value).lower()
        assert "RuntimeError" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_empty_response_text_raises_provider_error(self):
        """Empty response from Gemini raises StructuredOutputProviderError."""
        mock_response = MagicMock()
        mock_response.text = ""

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        provider = GeminiStructuredOutputProvider(api_key="mock-key", client=mock_client)

        with pytest.raises(StructuredOutputProviderError) as exc_info:
            await provider.generate_structured(prompt="Test", schema=SimpleTestEntity)

        assert "empty response or content was blocked" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_blocked_response_text_access_error(self):
        """When accessing response.text raises an exception (e.g. safety filter), raises provider error."""
        mock_response = MagicMock()
        type(mock_response).text = property(
            fget=MagicMock(side_effect=ValueError("Candidate was blocked due to safety"))
        )

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        provider = GeminiStructuredOutputProvider(api_key="mock-key", client=mock_client)

        with pytest.raises(StructuredOutputProviderError) as exc_info:
            await provider.generate_structured(prompt="Test", schema=SimpleTestEntity)

        assert "failed to read text from gemini response" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_upstream_malformed_json_raises_parse_error(self):
        """When Gemini returns non-JSON text, StructuredOutputParseError is raised."""
        mock_response = MagicMock()
        mock_response.text = "I am sorry, but I cannot format this as JSON."

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        provider = GeminiStructuredOutputProvider(api_key="mock-key", client=mock_client)

        with pytest.raises(StructuredOutputParseError) as exc_info:
            await provider.generate_structured(prompt="Test", schema=SimpleTestEntity)

        assert "failed to parse json" in str(exc_info.value).lower()
        assert exc_info.value.raw_output == "I am sorry, but I cannot format this as JSON."

    @pytest.mark.asyncio
    async def test_upstream_schema_mismatch_raises_validation_error(self):
        """When Gemini returns JSON that violates the schema, StructuredOutputValidationError is raised."""
        mock_response = MagicMock()
        mock_response.text = '{"unexpected_key": "some_value"}'

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        provider = GeminiStructuredOutputProvider(api_key="mock-key", client=mock_client)

        with pytest.raises(StructuredOutputValidationError) as exc_info:
            await provider.generate_structured(prompt="Test", schema=SimpleTestEntity)

        assert "failed schema validation" in str(exc_info.value).lower()
        assert len(exc_info.value.validation_errors) > 0


# ====================================================================
# 3. Factory & Dependency Injection Tests
# ====================================================================

class TestStructuredOutputFactory:
    """Unit tests verifying provider factory resolution and dependency injection."""

    def test_factory_resolves_gemini_provider(self):
        """Factory returns GeminiStructuredOutputProvider for 'gemini'."""
        mock_client = MagicMock()
        provider = get_structured_llm_provider(
            provider_type="gemini",
            api_key="mock-key",
            client=mock_client,
        )

        assert isinstance(provider, GeminiStructuredOutputProvider)
        assert isinstance(provider, StructuredLLMProvider)
        assert provider.model_name == "gemini-3.8-flash"

    def test_factory_respects_custom_model_and_temp(self):
        """Factory applies custom model name and temperature."""
        mock_client = MagicMock()
        provider = get_structured_llm_provider(
            provider_type="gemini",
            model_name="gemini-3.8-flash-custom",
            temperature=0.2,
            client=mock_client,
        )

        assert provider.model_name == "gemini-3.8-flash-custom"
        assert provider.temperature == 0.2

    def test_factory_unsupported_provider_raises_configuration_error(self):
        """Factory raises StructuredOutputConfigurationError for unknown provider types."""
        with pytest.raises(StructuredOutputConfigurationError) as exc_info:
            get_structured_llm_provider(provider_type="unknown-provider")

        assert "unsupported structured llm provider" in str(exc_info.value).lower()


# ====================================================================
# 4. Credential & Security Hygiene Tests
# ====================================================================

class TestSecurityHygiene:
    """Tests guaranteeing zero leakage of credentials or sensitive data."""

    def test_no_api_key_in_exception_strings(self, monkeypatch):
        """Verifies real or fake API keys do not appear in any exception string."""
        secret_key = "AIzaSySecretApiKey1234567890"

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=ValueError("Unauthorized access")
        )

        provider = GeminiStructuredOutputProvider(
            api_key=secret_key,
            client=mock_client,
        )

        # Ensure provider representation does not expose the key
        assert secret_key not in repr(provider)

        # Exception from call
        import asyncio

        with pytest.raises(StructuredOutputProviderError) as exc_info:
            asyncio.run(provider.generate_structured("prompt", SimpleTestEntity))

        assert secret_key not in str(exc_info.value)
