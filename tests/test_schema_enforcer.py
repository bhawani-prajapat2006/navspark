"""
Unit tests for schema enforcement and JSON extraction.
"""

import pytest

from compliance_clerk.llm.schema_enforcer import (
    extract_json_from_response,
    enforce_schema,
    build_retry_prompt,
    SchemaValidationError,
)
from compliance_clerk.models.schemas import NAOrderData, LeaseDeedData


class TestExtractJsonFromResponse:
    """Tests for JSON extraction from LLM responses."""

    def test_clean_json(self):
        raw = '{"key": "value"}'
        result = extract_json_from_response(raw)
        assert result == '{"key": "value"}'

    def test_json_in_code_fence(self):
        raw = '```json\n{"key": "value"}\n```'
        result = extract_json_from_response(raw)
        assert result == '{"key": "value"}'

    def test_json_in_plain_code_fence(self):
        raw = '```\n{"key": "value"}\n```'
        result = extract_json_from_response(raw)
        assert result == '{"key": "value"}'

    def test_json_with_surrounding_text(self):
        raw = 'Here is the data:\n{"key": "value"}\nHope this helps!'
        result = extract_json_from_response(raw)
        assert result == '{"key": "value"}'

    def test_no_json_raises_error(self):
        with pytest.raises(SchemaValidationError):
            extract_json_from_response("no json here at all")

    def test_json_with_whitespace(self):
        raw = '  \n  {"key": "value"}  \n  '
        result = extract_json_from_response(raw)
        assert '"key"' in result


class TestEnforceSchema:
    """Tests for full schema enforcement pipeline."""

    def test_valid_na_order(self):
        raw = '{"survey_number": "255", "village": "Rampura Mota", "area_in_na_order": 16534, "dated": "7/1/2026", "na_order_number": "iORA/31/02/112/7/2026"}'
        result = enforce_schema(raw, NAOrderData)
        assert isinstance(result, NAOrderData)
        assert result.survey_number == "255"
        assert result.area_in_na_order == 16534.0

    def test_valid_lease_deed(self):
        raw = '{"survey_number": "255", "lease_deed_doc_number": "837/2025", "lease_area": 16792, "lease_start_date": "28/05/2025"}'
        result = enforce_schema(raw, LeaseDeedData)
        assert isinstance(result, LeaseDeedData)
        assert result.lease_deed_doc_number == "837/2025"

    def test_code_fence_wrapped(self):
        raw = '```json\n{"survey_number": "256", "village": "Rampura Mota", "area_in_na_order": 5997, "dated": "16/02/2026", "na_order_number": "iORA/31/02/112/25/2026"}\n```'
        result = enforce_schema(raw, NAOrderData)
        assert result.survey_number == "256"

    def test_invalid_json_raises_error(self):
        with pytest.raises(SchemaValidationError) as exc_info:
            enforce_schema("not valid json", NAOrderData)
        assert "No JSON object found" in str(exc_info.value)

    def test_missing_field_raises_error(self):
        raw = '{"survey_number": "255"}'
        with pytest.raises(SchemaValidationError) as exc_info:
            enforce_schema(raw, NAOrderData)
        assert "validation failed" in str(exc_info.value).lower()

    def test_extra_text_around_json(self):
        raw = 'Extracted data:\n{"survey_number": "257", "village": "Rampura Mota", "area_in_na_order": 5997, "dated": "21/01/2026", "na_order_number": "iORA/31/02/112/9/2026"}\nDone.'
        result = enforce_schema(raw, NAOrderData)
        assert result.survey_number == "257"


class TestSchemaValidationError:
    """Tests for the custom exception."""

    def test_stores_raw_response(self):
        error = SchemaValidationError("test error", raw_response="raw text")
        assert error.raw_response == "raw text"

    def test_stores_errors_list(self):
        error = SchemaValidationError(
            "test", raw_response="raw", errors=["err1", "err2"]
        )
        assert len(error.errors) == 2

    def test_default_empty_errors(self):
        error = SchemaValidationError("test", raw_response="raw")
        assert error.errors == []


class TestBuildRetryPrompt:
    """Tests for retry prompt builder."""

    def test_includes_error_details(self):
        error = SchemaValidationError(
            "validation failed",
            raw_response='{"bad": "data"}',
            errors=["Field 'survey_number': required"],
        )
        prompt = build_retry_prompt("original prompt", '{"bad": "data"}', error)
        assert "survey_number" in prompt
        assert "original prompt" in prompt
        assert '{"bad": "data"}' in prompt
