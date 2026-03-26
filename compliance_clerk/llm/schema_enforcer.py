"""
Schema enforcement module for LLM response validation.

Extracts JSON from raw LLM responses (handling markdown code fences
and other formatting), validates against Pydantic models, and provides
structured error feedback for retry logic.
"""

import json
import re
import logging
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class SchemaValidationError(Exception):
    """Raised when LLM response fails schema validation."""

    def __init__(self, message: str, raw_response: str, errors: list = None):
        super().__init__(message)
        self.raw_response = raw_response
        self.errors = errors or []


def extract_json_from_response(raw_response: str) -> str:
    """
    Extract JSON string from an LLM response that may contain
    markdown code fences or extra text.

    Handles these patterns:
        1. ```json\n{...}\n```
        2. ```\n{...}\n```
        3. Raw JSON: {...}
        4. JSON with leading/trailing text

    Args:
        raw_response: Raw text response from the LLM.

    Returns:
        Cleaned JSON string.

    Raises:
        SchemaValidationError: If no valid JSON found.
    """
    text = raw_response.strip()

    # Pattern 1 & 2: Extract from markdown code fences
    code_fence_match = re.search(
        r"```(?:json)?\s*\n?(.*?)\n?\s*```",
        text,
        re.DOTALL,
    )
    if code_fence_match:
        return code_fence_match.group(1).strip()

    # Pattern 3 & 4: Find JSON object boundaries
    # Look for the first { and last } to extract the JSON object
    first_brace = text.find("{")
    last_brace = text.rfind("}")

    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1]

    raise SchemaValidationError(
        "No JSON object found in LLM response",
        raw_response=raw_response,
    )


def enforce_schema(raw_response: str, model_class: Type[T]) -> T:
    """
    Validate an LLM response against a Pydantic model.

    Steps:
        1. Extract JSON from the raw response
        2. Parse the JSON string
        3. Validate against the Pydantic model

    Args:
        raw_response: Raw text response from the LLM.
        model_class: The Pydantic model class to validate against.

    Returns:
        Validated Pydantic model instance.

    Raises:
        SchemaValidationError: If extraction, parsing, or validation fails.
    """
    # Step 1: Extract JSON
    try:
        json_str = extract_json_from_response(raw_response)
    except SchemaValidationError:
        raise

    # Step 2: Parse JSON
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise SchemaValidationError(
            f"Invalid JSON in LLM response: {e}",
            raw_response=raw_response,
            errors=[str(e)],
        )

    # Step 3: Validate against Pydantic model
    try:
        validated = model_class.model_validate(data)
        logger.info(f"Schema validation passed for {model_class.__name__}")
        return validated
    except ValidationError as e:
        error_details = []
        for error in e.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            error_details.append(f"  Field '{field}': {error['msg']}")

        error_msg = (
            f"Schema validation failed for {model_class.__name__}:\n"
            + "\n".join(error_details)
        )
        logger.warning(error_msg)

        raise SchemaValidationError(
            error_msg,
            raw_response=raw_response,
            errors=error_details,
        )


def build_retry_prompt(
    original_prompt: str,
    raw_response: str,
    error: SchemaValidationError,
) -> str:
    """
    Build a follow-up prompt when schema validation fails.

    Provides the LLM with its previous response and the specific
    validation errors so it can correct the output.

    Args:
        original_prompt: The original extraction prompt.
        raw_response: The LLM's previous raw response.
        error: The SchemaValidationError with details.

    Returns:
        A corrective prompt string.
    """
    error_list = "\n".join(error.errors) if error.errors else str(error)

    return f"""Your previous response had validation errors. Please fix and return ONLY valid JSON.

ERRORS FOUND:
{error_list}

YOUR PREVIOUS RESPONSE:
{raw_response}

ORIGINAL REQUEST:
{original_prompt}

Please return ONLY the corrected JSON object with no other text:"""


if __name__ == "__main__":
    """Quick test of schema enforcement."""
    from compliance_clerk.models.schemas import NAOrderData

    # Test 1: Clean JSON
    raw1 = '{"survey_number": "255", "village": "Rampura Mota", "area_in_na_order": 16534, "dated": "7/1/2026", "na_order_number": "iORA/31/02/112/7/2026"}'
    result1 = enforce_schema(raw1, NAOrderData)
    print(f"Test 1 (clean JSON): {result1.survey_number} ✓")

    # Test 2: JSON wrapped in code fences
    raw2 = '```json\n{"survey_number": "256", "village": "Rampura Mota", "area_in_na_order": 5997, "dated": "16/02/2026", "na_order_number": "iORA/31/02/112/25/2026"}\n```'
    result2 = enforce_schema(raw2, NAOrderData)
    print(f"Test 2 (code fences): {result2.survey_number} ✓")

    # Test 3: JSON with extra text
    raw3 = 'Here is the extracted data:\n{"survey_number": "257", "village": "Rampura Mota", "area_in_na_order": 5997, "dated": "21/01/2026", "na_order_number": "iORA/31/02/112/9/2026"}\nLet me know if you need more.'
    result3 = enforce_schema(raw3, NAOrderData)
    print(f"Test 3 (extra text):  {result3.survey_number} ✓")

    # Test 4: Invalid JSON
    try:
        enforce_schema("not json at all", NAOrderData)
    except SchemaValidationError as e:
        print(f"Test 4 (invalid):     Caught error ✓")

    print("\nAll schema enforcement tests passed!")
