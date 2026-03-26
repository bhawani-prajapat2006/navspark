"""
PDF text extraction and document classification module.

Uses pdfplumber to extract text from PDF files and classifies
documents as NA Orders, Lease Deeds, or eChallans based on
filename patterns. Also pairs related documents by Survey Number.
"""

import os
import re
from pathlib import Path
from typing import Optional

import pdfplumber

from compliance_clerk.config import (
    NA_ORDER_PATTERN,
    LEASE_DEED_PATTERN,
    ECHALLAN_PATTERN,
)


def extract_text_from_pdf(pdf_path: str | Path) -> str:
    """
    Extract all text content from a PDF file.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Combined text from all pages of the PDF.

    Raises:
        FileNotFoundError: If the PDF file does not exist.
        Exception: If pdfplumber fails to read the PDF.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    pages_text = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text:
                # Clean up common OCR/encoding artifacts
                text = _clean_extracted_text(text)
                pages_text.append(f"--- Page {page_num} ---\n{text}")

    return "\n\n".join(pages_text)


def _clean_extracted_text(text: str) -> str:
    """
    Clean common artifacts from extracted PDF text.

    Handles:
        - Excessive whitespace
        - Common CID (character ID) encoding artifacts
    """
    # Remove excessive whitespace (but keep newlines for structure)
    text = re.sub(r"[ \t]+", " ", text)
    # Remove standalone CID references that add no value
    text = re.sub(r"\(cid:\d+\)", "", text)
    # Clean up resulting double spaces
    text = re.sub(r"  +", " ", text)
    # Remove blank lines
    text = re.sub(r"\n\s*\n", "\n", text)

    return text.strip()


def classify_document(filename: str) -> Optional[str]:
    """
    Classify a PDF document type based on its filename.

    Args:
        filename: Name of the PDF file (not full path).

    Returns:
        Document type string: 'na_order', 'lease_deed', 'echallan',
        or None if unrecognized.
    """
    filename_upper = filename.upper()

    if NA_ORDER_PATTERN.upper() in filename_upper:
        return "na_order"
    elif LEASE_DEED_PATTERN.upper() in filename_upper:
        return "lease_deed"
    elif ECHALLAN_PATTERN.upper() in filename_upper:
        return "echallan"

    return None


def extract_survey_number(filename: str, doc_type: str) -> Optional[str]:
    """
    Extract the survey number from a document filename.

    Examples:
        '255 FINAL ORDER.pdf' -> '255'
        '251-p2 FINAL ORDER.pdf' -> '251p2'
        'Rampura Mota S.No.-255 Lease Deed No.-838.pdf' -> '255'
        'Rampura Mota S.No.- 251p2 Lease Deed No.- 141.pdf' -> '251p2'

    Args:
        filename: Name of the PDF file.
        doc_type: Type of document ('na_order' or 'lease_deed').

    Returns:
        Extracted survey number string, or None if not found.
    """
    if doc_type == "na_order":
        # Pattern: "<survey_number> FINAL ORDER.pdf"
        # e.g., "255 FINAL ORDER.pdf" or "251-p2 FINAL ORDER.pdf"
        match = re.match(r"^([\w\-]+)\s+FINAL ORDER", filename)
        if match:
            # Normalize: remove hyphens (251-p2 -> 251p2)
            return match.group(1).replace("-", "")

    elif doc_type == "lease_deed":
        # Pattern: "Rampura Mota S.No.-<survey_no> Lease Deed No.-<deed_no>.pdf"
        match = re.search(r"S\.No\.[-\s]*(\w+)\s+Lease Deed", filename)
        if match:
            return match.group(1).strip()

    return None


def extract_lease_deed_number(filename: str) -> Optional[str]:
    """
    Extract the Lease Deed document number from the filename.

    Example:
        'Rampura Mota S.No.-255 Lease Deed No.-838.pdf' -> '838'

    Args:
        filename: Name of the Lease Deed PDF file.

    Returns:
        Lease deed number string, or None if not found.
    """
    match = re.search(r"Lease Deed No\.[-\s]*(\d+)", filename)
    if match:
        return match.group(1)
    return None


def get_paired_documents(input_dir: str | Path) -> list[dict]:
    """
    Scan the input directory and pair NA Orders with their
    corresponding Lease Deeds based on Survey Number.

    Args:
        input_dir: Path to the directory containing PDF files.

    Returns:
        List of dicts, each containing:
            - survey_number: str
            - na_order_path: Path (or None)
            - na_order_filename: str (or None)
            - lease_deed_path: Path (or None)  
            - lease_deed_filename: str (or None)
    """
    input_dir = Path(input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    # Collect all PDF files and classify them
    na_orders = {}  # survey_number -> file info
    lease_deeds = {}  # survey_number -> file info

    for pdf_file in sorted(input_dir.glob("*.pdf*")):
        filename = pdf_file.name
        doc_type = classify_document(filename)

        if doc_type == "na_order":
            survey_no = extract_survey_number(filename, doc_type)
            if survey_no:
                na_orders[survey_no] = {
                    "path": pdf_file,
                    "filename": filename,
                }

        elif doc_type == "lease_deed":
            survey_no = extract_survey_number(filename, doc_type)
            if survey_no:
                lease_deeds[survey_no] = {
                    "path": pdf_file,
                    "filename": filename,
                }

    # Merge by survey number
    all_survey_numbers = sorted(set(list(na_orders.keys()) + list(lease_deeds.keys())))

    paired = []
    for survey_no in all_survey_numbers:
        na = na_orders.get(survey_no)
        ld = lease_deeds.get(survey_no)

        paired.append({
            "survey_number": survey_no,
            "na_order_path": na["path"] if na else None,
            "na_order_filename": na["filename"] if na else None,
            "lease_deed_path": ld["path"] if ld else None,
            "lease_deed_filename": ld["filename"] if ld else None,
        })

    return paired


if __name__ == "__main__":
    """Quick test of PDF extraction and pairing."""
    from compliance_clerk.config import INPUT_DIR

    print("=== Document Classification & Pairing ===\n")
    pairs = get_paired_documents(INPUT_DIR)

    for pair in pairs:
        print(f"Survey No: {pair['survey_number']}")
        print(f"  NA Order  : {pair['na_order_filename'] or 'NOT FOUND'}")
        print(f"  Lease Deed: {pair['lease_deed_filename'] or 'NOT FOUND'}")
        print()

    # Test text extraction on first NA Order found
    if pairs and pairs[0]["na_order_path"]:
        path = pairs[0]["na_order_path"]
        print(f"=== Text Preview: {path.name} ===\n")
        text = extract_text_from_pdf(path)
        print(text[:1000])
        print("...")
