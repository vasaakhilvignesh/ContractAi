"""
ContractIQ — Structured Output Validation Infrastructure (Phase 6A)

Provides reusable, provider-independent validation for LLM responses.
Converts raw LLM text into strictly validated Pydantic models.

Guarantees:
  - Strict validation against any Pydantic BaseModel schema.
  - Robust stripping of markdown code blocks (```json ... ``` or ``` ... ```).
  - Explicit custom exception hierarchy distinguishing parse errors from schema validation errors.
  - No credential or raw secret exposure in error summaries.
  - Detailed, structured error context (field paths, messages, raw outputs).
"""

import json
import logging
import re
from typing import Any, Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# ====================================================================
# Exception Hierarchy
# ====================================================================

class StructuredOutputError(Exception):
    """Base exception for all structured output operations."""
    pass


class StructuredOutputConfigurationError(StructuredOutputError):
    """Raised when an LLM provider is misconfigured or missing credentials."""
    pass


class StructuredOutputProviderError(StructuredOutputError):
    """Raised when an upstream LLM API call fails, times out, or returns an empty/blocked response."""
    pass


class StructuredOutputParseError(StructuredOutputError):
    """
    Raised when LLM output cannot be parsed into valid JSON.
    Carries the raw response text for debugging and telemetry.
    """

    def __init__(self, message: str, raw_output: str | None = None) -> None:
        super().__init__(message)
        self.raw_output = raw_output


class StructuredOutputValidationError(StructuredOutputError):
    """
    Raised when LLM output is valid JSON but violates the Pydantic schema.
    Carries structured field error details and the raw response text.
    """

    def __init__(
        self,
        message: str,
        validation_errors: list[dict[str, Any]] | None = None,
        raw_output: str | None = None,
    ) -> None:
        super().__init__(message)
        self.validation_errors = validation_errors or []
        self.raw_output = raw_output


# ====================================================================
# JSON Extraction & Sanitization
# ====================================================================

_FENCE_REGEX = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def clean_json_text(text: str | None) -> str:
    """
    Extracts and normalizes JSON text from raw LLM output.
    
    Handles:
      - Clean JSON payloads.
      - Markdown code blocks (```json ... ``` or ``` ... ```).
      - Surrounding preamble/postamble commentary outside code fences.
      - Leading and trailing whitespace.
    """
    if text is None:
        return ""

    stripped = text.strip()
    if not stripped:
        return ""

    # Check for markdown code fences first
    match = _FENCE_REGEX.search(stripped)
    if match:
        fenced_content = match.group(1).strip()
        if fenced_content:
            return fenced_content

    # If starts with ``` but regex didn't find closing fence (unclosed code fence)
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1 :].strip()
        else:
            stripped = stripped.lstrip("`").strip()

    return stripped


def _find_outermost_json_substring(text: str) -> str | None:
    """
    Attempts to locate the outermost matching braces ({...} or [...])
    in text that contains surrounding commentary without code fences.
    """
    first_brace = text.find("{")
    first_bracket = text.find("[")

    start_idx = -1
    close_char = ""

    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        start_idx = first_brace
        close_char = "}"
    elif first_bracket != -1:
        start_idx = first_bracket
        close_char = "]"

    if start_idx == -1:
        return None

    last_idx = text.rfind(close_char)
    if last_idx > start_idx:
        return text[start_idx : last_idx + 1]

    return None


# ====================================================================
# Core Validation Function
# ====================================================================

def validate_structured_output(
    raw_text: str | None,
    schema: Type[T],
    strict: bool = False,
) -> T:
    """
    Validates raw LLM response text strictly against a Pydantic model schema T.

    Args:
        raw_text: The raw output string returned by the LLM.
        schema: Target Pydantic model class (subclass of BaseModel).
        strict: If True, enables strict mode in Pydantic validation.

    Returns:
        A validated instance of T.

    Raises:
        StructuredOutputParseError: If raw_text is empty, missing, or malformed JSON.
        StructuredOutputValidationError: If raw_text is valid JSON but violates schema T.
    """
    if not isinstance(schema, type) or not issubclass(schema, BaseModel):
        raise StructuredOutputValidationError(
            f"Schema must be a Pydantic BaseModel subclass, got {schema!r}."
        )

    if raw_text is None or not raw_text.strip():
        raise StructuredOutputParseError(
            "LLM returned an empty or whitespace-only response.",
            raw_output=raw_text,
        )

    cleaned = clean_json_text(raw_text)

    # Attempt standard JSON decode
    parsed_data: Any = None
    try:
        parsed_data = json.loads(cleaned)
    except json.JSONDecodeError as primary_err:
        # Fallback: attempt to find outermost {...} or [...] if there was surrounding commentary
        candidate = _find_outermost_json_substring(cleaned)
        if candidate and candidate != cleaned:
            try:
                parsed_data = json.loads(candidate)
            except json.JSONDecodeError:
                parsed_data = None

        if parsed_data is None:
            raise StructuredOutputParseError(
                f"Failed to parse JSON from LLM response: {primary_err.msg} (line {primary_err.lineno}, col {primary_err.colno})",
                raw_output=raw_text,
            ) from primary_err

    # Validate against Pydantic schema
    try:
        return schema.model_validate(parsed_data, strict=strict)
    except ValidationError as val_err:
        formatted_errors: list[dict[str, Any]] = []
        summary_parts: list[str] = []

        for err in val_err.errors():
            loc_str = " -> ".join(str(elem) for elem in err.get("loc", ())) or "<root>"
            msg = err.get("msg", "Invalid value")
            err_type = err.get("type", "value_error")
            formatted_errors.append({
                "loc": loc_str,
                "msg": msg,
                "type": err_type,
            })
            summary_parts.append(f"{loc_str}: {msg}")

        error_summary = "; ".join(summary_parts)
        raise StructuredOutputValidationError(
            f"Structured output failed schema validation for {schema.__name__}: {error_summary}",
            validation_errors=formatted_errors,
            raw_output=raw_text,
        ) from val_err
