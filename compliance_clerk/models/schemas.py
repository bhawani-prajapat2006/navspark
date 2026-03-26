"""
Pydantic data models for document extraction schemas.

Defines strict schemas for each document type (NA Order, Lease Deed,
eChallan) and a consolidated output model. These models enforce
valid JSON structure from LLM responses via Pydantic validation.
"""

from pydantic import BaseModel, Field
from typing import Optional


class NAOrderData(BaseModel):
    """Schema for fields extracted from NA (Non-Agricultural) Permission Order PDFs."""

    survey_number: str = Field(
        ..., description="Survey/Block number of the land (e.g., '255', '251/p2')"
    )
    village: str = Field(
        ..., description="Village name where the land is located (e.g., 'Rampura Mota')"
    )
    area_in_na_order: float = Field(
        ..., description="Land area mentioned in the NA order in sq. meters"
    )
    dated: str = Field(
        ..., description="Date of the NA order in DD/MM/YYYY format"
    )
    na_order_number: str = Field(
        ..., description="Official NA order number (e.g., 'iORA/31/02/112/7/2026')"
    )


class LeaseDeedData(BaseModel):
    """Schema for fields extracted from Lease Deed PDFs."""

    survey_number: str = Field(
        ..., description="Survey/Block number of the land (e.g., '255', '251/p2')"
    )
    lease_deed_doc_number: str = Field(
        ..., description="Lease deed document/registration number"
    )
    lease_area: float = Field(
        ..., description="Lease area in sq. meters"
    )
    lease_start_date: str = Field(
        ..., description="Lease start date in DD/MM/YYYY format"
    )


class EChallanData(BaseModel):
    """Schema for fields extracted from eChallan documents."""

    challan_number: str = Field(
        ..., description="Unique challan identifier"
    )
    vehicle_number: str = Field(
        ..., description="Vehicle registration number"
    )
    violation_date: str = Field(
        ..., description="Date of the traffic violation in DD/MM/YYYY format"
    )
    amount: float = Field(
        ..., description="Fine/penalty amount in INR"
    )
    offence_description: str = Field(
        ..., description="Description of the traffic offence"
    )
    payment_status: str = Field(
        ..., description="Payment status (e.g., 'Paid', 'Unpaid', 'Pending')"
    )


class ConsolidatedRow(BaseModel):
    """
    Consolidated output row combining NA Order and Lease Deed data.

    This matches the expected Excel output format with columns:
    Sr.no. | Village | Survey No. | Area in NA Order | Dated |
    NA Order No. | Lease Deed Doc. No. | Lease Area | Lease Start
    """

    sr_no: int = Field(
        ..., description="Serial number (row index)"
    )
    village: str = Field(
        ..., description="Village name"
    )
    survey_number: str = Field(
        ..., description="Survey/Block number"
    )
    area_in_na_order: float = Field(
        ..., description="Land area from NA order in sq. meters"
    )
    dated: str = Field(
        ..., description="NA order date"
    )
    na_order_number: str = Field(
        ..., description="Official NA order number"
    )
    lease_deed_doc_number: str = Field(
        default="", description="Lease deed document number"
    )
    lease_area: float = Field(
        default=0.0, description="Lease area in sq. meters"
    )
    lease_start: str = Field(
        default="", description="Lease start date"
    )

    def to_excel_dict(self) -> dict:
        """Convert to dictionary with Excel-friendly column names."""
        return {
            "Sr.no.": self.sr_no,
            "Village": self.village,
            "Survey No.": self.survey_number,
            "Area in NA Order": self.area_in_na_order,
            "Dated": self.dated,
            "NA Order No.": self.na_order_number,
            "Lease Deed Doc. No.": self.lease_deed_doc_number,
            "Lease Area": self.lease_area,
            "Lease Start": self.lease_start,
        }


# Map document types to their Pydantic model classes
SCHEMA_MAP = {
    "na_order": NAOrderData,
    "lease_deed": LeaseDeedData,
    "echallan": EChallanData,
}
