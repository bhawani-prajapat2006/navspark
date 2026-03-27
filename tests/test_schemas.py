"""
Unit tests for Pydantic data models and schema validation.
"""

import pytest

from compliance_clerk.models.schemas import (
    NAOrderData,
    LeaseDeedData,
    EChallanData,
    ConsolidatedRow,
    SCHEMA_MAP,
)
from pydantic import ValidationError


class TestNAOrderData:
    """Tests for NA Order data model."""

    def test_valid_na_order(self):
        data = NAOrderData(
            survey_number="255",
            village="Rampura Mota",
            area_in_na_order=16534.0,
            dated="7/1/2026",
            na_order_number="iORA/31/02/112/7/2026",
        )
        assert data.survey_number == "255"
        assert data.village == "Rampura Mota"
        assert data.area_in_na_order == 16534.0

    def test_area_coerced_to_float(self):
        data = NAOrderData(
            survey_number="256",
            village="Rampura Mota",
            area_in_na_order=5997,  # int should be coerced
            dated="16/02/2026",
            na_order_number="iORA/31/02/112/25/2026",
        )
        assert isinstance(data.area_in_na_order, float)

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            NAOrderData(
                survey_number="255",
                village="Rampura Mota",
                # missing area_in_na_order, dated, na_order_number
            )


class TestLeaseDeedData:
    """Tests for Lease Deed data model."""

    def test_valid_lease_deed(self):
        data = LeaseDeedData(
            survey_number="255",
            lease_deed_doc_number="837/2025",
            lease_area=16792.0,
            lease_start_date="28/05/2025",
        )
        assert data.lease_deed_doc_number == "837/2025"
        assert data.lease_area == 16792.0

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            LeaseDeedData(
                survey_number="255",
                # missing other fields
            )


class TestEChallanData:
    """Tests for eChallan data model."""

    def test_valid_echallan(self):
        data = EChallanData(
            challan_number="CH123456",
            vehicle_number="GJ 01 AB 1234",
            violation_date="15/03/2026",
            amount=500.0,
            offence_description="Signal jumping",
            payment_status="Unpaid",
        )
        assert data.challan_number == "CH123456"
        assert data.amount == 500.0


class TestConsolidatedRow:
    """Tests for the consolidated output row model."""

    def test_valid_row(self):
        row = ConsolidatedRow(
            sr_no=1,
            village="Rampura Mota",
            survey_number="257",
            area_in_na_order=16534,
            dated="7/1/2026",
            na_order_number="iORA/31/02/112/7/2026",
            lease_deed_doc_number="837/2025",
            lease_area=16792,
            lease_start="28/05/2025",
        )
        assert row.sr_no == 1

    def test_optional_lease_fields(self):
        """Lease deed fields should have defaults."""
        row = ConsolidatedRow(
            sr_no=1,
            village="Rampura Mota",
            survey_number="257",
            area_in_na_order=16534,
            dated="7/1/2026",
            na_order_number="iORA/31/02/112/7/2026",
        )
        assert row.lease_deed_doc_number == ""
        assert row.lease_area == 0.0
        assert row.lease_start == ""

    def test_to_excel_dict(self):
        row = ConsolidatedRow(
            sr_no=1,
            village="Rampura Mota",
            survey_number="257",
            area_in_na_order=16534,
            dated="7/1/2026",
            na_order_number="iORA/31/02/112/7/2026",
        )
        d = row.to_excel_dict()
        assert d["Sr.no."] == 1
        assert d["Village"] == "Rampura Mota"
        assert d["Survey No."] == "257"
        assert "NA Order No." in d
        assert "Lease Deed Doc. No." in d

    def test_excel_dict_has_all_columns(self):
        row = ConsolidatedRow(
            sr_no=1, village="V", survey_number="1",
            area_in_na_order=100, dated="1/1/2026",
            na_order_number="ORD-1",
        )
        expected_keys = {
            "Sr.no.", "Village", "Survey No.", "Area in NA Order",
            "Dated", "NA Order No.", "Lease Deed Doc. No.",
            "Lease Area", "Lease Start",
        }
        assert set(row.to_excel_dict().keys()) == expected_keys


class TestSchemaMap:
    """Tests for the SCHEMA_MAP registry."""

    def test_all_types_registered(self):
        assert "na_order" in SCHEMA_MAP
        assert "lease_deed" in SCHEMA_MAP
        assert "echallan" in SCHEMA_MAP

    def test_correct_model_classes(self):
        assert SCHEMA_MAP["na_order"] is NAOrderData
        assert SCHEMA_MAP["lease_deed"] is LeaseDeedData
        assert SCHEMA_MAP["echallan"] is EChallanData
