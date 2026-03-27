"""
Unit tests for PDF text extraction and document classification.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from compliance_clerk.parsers.pdf_extractor import (
    classify_document,
    extract_survey_number,
    extract_lease_deed_number,
    _clean_extracted_text,
)


class TestClassifyDocument:
    """Tests for document classification based on filename."""

    def test_na_order_classification(self):
        assert classify_document("255 FINAL ORDER.pdf") == "na_order"

    def test_na_order_with_prefix(self):
        assert classify_document("251-p2 FINAL ORDER.pdf") == "na_order"

    def test_lease_deed_classification(self):
        assert classify_document("Rampura Mota S.No.-255 Lease Deed No.-838.pdf") == "lease_deed"

    def test_lease_deed_with_spaces(self):
        assert classify_document("Rampura Mota S.No.- 251p2 Lease Deed No.- 141.pdf") == "lease_deed"

    def test_echallan_classification(self):
        assert classify_document("traffic_challan_2026.pdf") == "echallan"

    def test_unknown_document(self):
        assert classify_document("random_document.pdf") is None

    def test_case_insensitive(self):
        assert classify_document("255 final order.pdf") == "na_order"
        assert classify_document("LEASE DEED document.pdf") == "lease_deed"


class TestExtractSurveyNumber:
    """Tests for survey number extraction from filenames."""

    def test_simple_na_order(self):
        result = extract_survey_number("255 FINAL ORDER.pdf", "na_order")
        assert result == "255"

    def test_compound_na_order(self):
        result = extract_survey_number("251-p2 FINAL ORDER.pdf", "na_order")
        assert result == "251p2"

    def test_na_order_256(self):
        result = extract_survey_number("256 FINAL ORDER.pdf", "na_order")
        assert result == "256"

    def test_na_order_257(self):
        result = extract_survey_number("257 FINAL ORDER.pdf", "na_order")
        assert result == "257"

    def test_lease_deed_simple(self):
        result = extract_survey_number(
            "Rampura Mota S.No.-255 Lease Deed No.-838.pdf", "lease_deed"
        )
        assert result == "255"

    def test_lease_deed_with_spaces(self):
        result = extract_survey_number(
            "Rampura Mota S.No.- 251p2 Lease Deed No.- 141.pdf", "lease_deed"
        )
        assert result == "251p2"

    def test_unknown_type_returns_none(self):
        result = extract_survey_number("255 FINAL ORDER.pdf", "unknown")
        assert result is None


class TestExtractLeaseDeedNumber:
    """Tests for lease deed document number extraction."""

    def test_simple_deed_number(self):
        result = extract_lease_deed_number("Rampura Mota S.No.-255 Lease Deed No.-838.pdf")
        assert result == "838"

    def test_deed_number_with_spaces(self):
        result = extract_lease_deed_number("Rampura Mota S.No.- 251p2 Lease Deed No.- 141.pdf")
        assert result == "141"

    def test_no_deed_number(self):
        result = extract_lease_deed_number("random_document.pdf")
        assert result is None


class TestCleanExtractedText:
    """Tests for text cleaning function."""

    def test_removes_cid_artifacts(self):
        text = "Hello (cid:88) World (cid:136)"
        result = _clean_extracted_text(text)
        assert "(cid:" not in result
        assert "Hello" in result
        assert "World" in result

    def test_collapses_whitespace(self):
        text = "Hello    World   Test"
        result = _clean_extracted_text(text)
        assert "  " not in result

    def test_removes_blank_lines(self):
        text = "Line 1\n\n\nLine 2"
        result = _clean_extracted_text(text)
        assert "\n\n" not in result

    def test_strips_text(self):
        text = "  Hello World  "
        result = _clean_extracted_text(text)
        assert result == "Hello World"
