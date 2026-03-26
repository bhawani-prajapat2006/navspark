"""
Main extraction pipeline orchestrating the full document processing flow.

Ties together: PDF parsing → LLM extraction → schema validation → audit logging.
Processes paired NA Order and Lease Deed documents, producing consolidated rows.
"""

import logging
from pathlib import Path
from typing import Optional

from compliance_clerk.parsers.pdf_extractor import (
    extract_text_from_pdf,
    get_paired_documents,
    extract_lease_deed_number,
)
from compliance_clerk.llm.client import LLMClient, LLMClientError
from compliance_clerk.llm.prompts import PROMPT_MAP
from compliance_clerk.llm.schema_enforcer import (
    enforce_schema,
    build_retry_prompt,
    SchemaValidationError,
)
from compliance_clerk.models.schemas import (
    NAOrderData,
    LeaseDeedData,
    ConsolidatedRow,
    SCHEMA_MAP,
)
from compliance_clerk.audit.logger import AuditLogger
from compliance_clerk.config import INPUT_DIR, LLM_MAX_RETRIES

logger = logging.getLogger(__name__)


class ExtractionPipeline:
    """
    Orchestrates the full document extraction workflow.

    Flow:
        1. Scan input directory for PDFs
        2. Classify and pair documents (NA Order ↔ Lease Deed)
        3. Extract text from each PDF via pdfplumber
        4. Send text to LLM with appropriate prompts
        5. Validate LLM response against Pydantic schemas
        6. Log everything to the audit trail
        7. Return consolidated rows for report generation
    """

    def __init__(
        self,
        input_dir: Optional[str | Path] = None,
        llm_client: Optional[LLMClient] = None,
        audit_logger: Optional[AuditLogger] = None,
    ):
        """
        Initialize the extraction pipeline.

        Args:
            input_dir: Directory containing PDF files.
            llm_client: Pre-configured LLM client (created if not provided).
            audit_logger: Pre-configured audit logger (created if not provided).
        """
        self.input_dir = Path(input_dir or INPUT_DIR)
        self.llm_client = llm_client or LLMClient()
        self.audit_logger = audit_logger or AuditLogger()

        logger.info(f"Pipeline initialized. Input dir: {self.input_dir}")

    def _extract_with_retry(
        self,
        text: str,
        doc_type: str,
        doc_name: str,
    ) -> Optional[dict]:
        """
        Extract data from document text using LLM with retry on validation failure.

        Args:
            text: Extracted PDF text.
            doc_type: Document type ('na_order', 'lease_deed', 'echallan').
            doc_name: Filename for logging.

        Returns:
            Validated data as dict, or None if all attempts fail.
        """
        prompt_builder = PROMPT_MAP.get(doc_type)
        model_class = SCHEMA_MAP.get(doc_type)

        if not prompt_builder or not model_class:
            logger.error(f"Unknown document type: {doc_type}")
            return None

        prompt = prompt_builder(text)
        last_error = None

        for attempt in range(1, LLM_MAX_RETRIES + 1):
            try:
                # Call LLM
                raw_response = self.llm_client.generate(prompt)

                # Validate response
                validated = enforce_schema(raw_response, model_class)

                # Log success
                self.audit_logger.log_extraction(
                    document_name=doc_name,
                    document_type=doc_type,
                    prompt=prompt,
                    raw_response=raw_response,
                    parsed_json=validated.model_dump(),
                    status="success",
                    attempt_number=attempt,
                )

                logger.info(f"✓ Extracted {doc_type} from {doc_name} (attempt {attempt})")
                return validated.model_dump()

            except SchemaValidationError as e:
                last_error = e
                logger.warning(
                    f"Validation failed for {doc_name} (attempt {attempt}): {e}"
                )

                # Log the failed attempt
                self.audit_logger.log_extraction(
                    document_name=doc_name,
                    document_type=doc_type,
                    prompt=prompt,
                    raw_response=e.raw_response,
                    status="validation_error",
                    error_message=str(e),
                    attempt_number=attempt,
                )

                # Build retry prompt with error feedback
                if attempt < LLM_MAX_RETRIES:
                    prompt = build_retry_prompt(prompt, e.raw_response, e)

            except LLMClientError as e:
                last_error = e
                logger.error(f"LLM error for {doc_name}: {e}")

                self.audit_logger.log_extraction(
                    document_name=doc_name,
                    document_type=doc_type,
                    prompt=prompt,
                    status="llm_error",
                    error_message=str(e),
                    attempt_number=attempt,
                )
                break  # Don't retry on LLM client errors (already retried internally)

        logger.error(f"✗ Failed to extract {doc_type} from {doc_name}: {last_error}")
        return None

    def run(self) -> list[ConsolidatedRow]:
        """
        Execute the full extraction pipeline.

        Returns:
            List of ConsolidatedRow objects ready for report generation.
        """
        logger.info("=" * 50)
        logger.info("Starting extraction pipeline")
        logger.info("=" * 50)

        # Step 1: Discover and pair documents
        pairs = get_paired_documents(self.input_dir)
        logger.info(f"Found {len(pairs)} document pair(s)")

        if not pairs:
            logger.warning("No document pairs found in input directory")
            return []

        consolidated_rows = []

        for idx, pair in enumerate(pairs, start=1):
            survey_no = pair["survey_number"]
            logger.info(f"\n--- Processing pair {idx}: Survey No. {survey_no} ---")

            na_data = None
            ld_data = None

            # Step 2: Extract NA Order
            if pair["na_order_path"]:
                logger.info(f"Extracting NA Order: {pair['na_order_filename']}")
                try:
                    na_text = extract_text_from_pdf(pair["na_order_path"])
                    na_data = self._extract_with_retry(
                        na_text, "na_order", pair["na_order_filename"]
                    )
                except Exception as e:
                    logger.error(f"Failed to read {pair['na_order_filename']}: {e}")
            else:
                logger.warning(f"No NA Order found for Survey No. {survey_no}")

            # Step 3: Extract Lease Deed
            if pair["lease_deed_path"]:
                logger.info(f"Extracting Lease Deed: {pair['lease_deed_filename']}")
                try:
                    ld_text = extract_text_from_pdf(pair["lease_deed_path"])
                    ld_data = self._extract_with_retry(
                        ld_text, "lease_deed", pair["lease_deed_filename"]
                    )
                except Exception as e:
                    logger.error(f"Failed to read {pair['lease_deed_filename']}: {e}")
            else:
                logger.warning(f"No Lease Deed found for Survey No. {survey_no}")

            # Step 4: Consolidate into output row
            if na_data:
                row = ConsolidatedRow(
                    sr_no=idx,
                    village=na_data.get("village", ""),
                    survey_number=na_data.get("survey_number", survey_no),
                    area_in_na_order=na_data.get("area_in_na_order", 0.0),
                    dated=na_data.get("dated", ""),
                    na_order_number=na_data.get("na_order_number", ""),
                    lease_deed_doc_number=(
                        ld_data.get("lease_deed_doc_number", "")
                        if ld_data
                        else extract_lease_deed_number(pair.get("lease_deed_filename", "") or "") or ""
                    ),
                    lease_area=ld_data.get("lease_area", 0.0) if ld_data else 0.0,
                    lease_start=ld_data.get("lease_start_date", "") if ld_data else "",
                )
                consolidated_rows.append(row)
                logger.info(f"✓ Row {idx} consolidated for Survey No. {survey_no}")
            else:
                logger.warning(f"Skipping Survey No. {survey_no} — NA Order extraction failed")

        # Summary
        logger.info("=" * 50)
        logger.info(f"Pipeline complete: {len(consolidated_rows)}/{len(pairs)} rows extracted")
        stats = self.audit_logger.get_stats()
        logger.info(f"Audit stats: {stats}")
        logger.info("=" * 50)

        return consolidated_rows


if __name__ == "__main__":
    """Quick test — runs pipeline on the input directory."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    pipeline = ExtractionPipeline()
    rows = pipeline.run()

    print(f"\n=== Results: {len(rows)} rows ===")
    for row in rows:
        print(row.to_excel_dict())
