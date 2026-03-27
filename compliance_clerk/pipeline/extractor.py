"""
Main extraction pipeline orchestrating the full document processing flow.

Ties together: PDF → LLM multimodal extraction → schema validation → audit logging.
Sends PDF files directly to Gemini's vision API for reading scanned
and CID-encoded documents that pdfplumber cannot extract text from.
"""

import time
import logging
from pathlib import Path
from typing import Optional

from compliance_clerk.parsers.pdf_extractor import (
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
        3. Send PDF files directly to Gemini multimodal API
        4. Validate LLM response against Pydantic schemas
        5. Log everything to the audit trail
        6. Return consolidated rows for report generation
    """

    def __init__(
        self,
        input_dir: Optional[str | Path] = None,
        llm_client: Optional[LLMClient] = None,
        audit_logger: Optional[AuditLogger] = None,
        incremental: bool = False,
    ):
        self.input_dir = Path(input_dir or INPUT_DIR)
        self.llm_client = llm_client or LLMClient()
        self.audit_logger = audit_logger or AuditLogger()
        self.incremental = incremental

        logger.info(f"Pipeline initialized. Input dir: {self.input_dir}")
        if self.incremental:
            logger.info("Incremental mode ON — will skip already-processed documents")

    def _extract_with_retry(
        self,
        pdf_path: str,
        doc_type: str,
        doc_name: str,
    ) -> Optional[dict]:
        """
        Extract data from a PDF using LLM multimodal API with retry on validation failure.

        Sends the actual PDF file to Gemini's vision API instead of extracting
        text first. This handles scanned PDFs and CID-encoded fonts.

        Args:
            pdf_path: Path to the PDF file.
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

        # Build prompt with empty text (the PDF itself provides the content)
        prompt = prompt_builder("")
        last_error = None

        for attempt in range(1, LLM_MAX_RETRIES + 1):
            try:
                # Send PDF directly to multimodal API (or text-only for demo mode)
                if hasattr(self.llm_client, 'generate_with_pdf'):
                    raw_response = self.llm_client.generate_with_pdf(prompt, pdf_path)
                else:
                    raw_response = self.llm_client.generate(prompt)

                # Validate response
                validated = enforce_schema(raw_response, model_class)

                # Log success
                self.audit_logger.log_extraction(
                    document_name=doc_name,
                    document_type=doc_type,
                    prompt=prompt[:500],
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

                self.audit_logger.log_extraction(
                    document_name=doc_name,
                    document_type=doc_type,
                    prompt=prompt[:500],
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
                    prompt=prompt[:500],
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

        # Incremental mode: get already-processed documents
        processed_docs = set()
        if self.incremental:
            processed_docs = self.audit_logger.get_processed_documents()
            logger.info(f"Incremental mode: {len(processed_docs)} documents already processed")

        consolidated_rows = []

        for idx, pair in enumerate(pairs, start=1):
            survey_no = pair["survey_number"]
            logger.info(f"\n--- Processing pair {idx}: Survey No. {survey_no} ---")

            na_data = None
            ld_data = None

            # Step 2: Extract NA Order
            na_filename = pair.get("na_order_filename", "")
            if pair["na_order_path"]:
                if self.incremental and na_filename in processed_docs:
                    na_data = self.audit_logger.get_cached_results(na_filename, "na_order")
                    logger.info(f"⏩ Skipping NA Order (cached): {na_filename}")
                else:
                    logger.info(f"Extracting NA Order: {na_filename}")
                    try:
                        na_data = self._extract_with_retry(
                            pair["na_order_path"], "na_order", na_filename
                        )
                    except Exception as e:
                        logger.error(f"Failed to process {na_filename}: {e}")
            else:
                logger.warning(f"No NA Order found for Survey No. {survey_no}")

            # Rate limit: pause between LLM calls for free tier (skip in demo/incremental-cached mode)
            from compliance_clerk.llm.demo_responses import DemoLLMClient
            ld_filename = pair.get("lease_deed_filename", "")
            needs_ld_extraction = pair["lease_deed_path"] and not (self.incremental and ld_filename in processed_docs)
            if needs_ld_extraction and not isinstance(self.llm_client, DemoLLMClient):
                logger.info("Pausing 60s between LLM calls (free tier rate limit)...")
                time.sleep(60)

            # Step 3: Extract Lease Deed
            if pair["lease_deed_path"]:
                if self.incremental and ld_filename in processed_docs:
                    ld_data = self.audit_logger.get_cached_results(ld_filename, "lease_deed")
                    logger.info(f"⏩ Skipping Lease Deed (cached): {ld_filename}")
                else:
                    logger.info(f"Extracting Lease Deed: {ld_filename}")
                    try:
                        ld_data = self._extract_with_retry(
                            pair["lease_deed_path"], "lease_deed", ld_filename
                        )
                    except Exception as e:
                        logger.error(f"Failed to process {ld_filename}: {e}")
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
