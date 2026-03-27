"""
Centralized configuration for The Compliance Clerk pipeline.

Loads environment variables from .env file and provides
all paths, LLM settings, and pipeline parameters.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ──────────────────────────────────────────────
# Directory Paths
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────
# LLM Configuration (Google Gemini)
# ──────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_MODEL_NAME = "gemini-2.5-flash"
LLM_TEMPERATURE = 0.1  # Low temperature for deterministic extraction
LLM_MAX_RETRIES = 3    # Retry attempts on failure
LLM_RETRY_DELAY = 45   # Base delay in seconds (handles per-minute rate limits)

# ──────────────────────────────────────────────
# Audit Trail Configuration
# ──────────────────────────────────────────────
AUDIT_DB_PATH = DATA_DIR / "audit_log.db"

# ──────────────────────────────────────────────
# Output Configuration
# ──────────────────────────────────────────────
DEFAULT_OUTPUT_FILENAME = "output.xlsx"
DEFAULT_OUTPUT_PATH = OUTPUT_DIR / DEFAULT_OUTPUT_FILENAME

# ──────────────────────────────────────────────
# Document Classification Patterns
# ──────────────────────────────────────────────
NA_ORDER_PATTERN = "FINAL ORDER"
LEASE_DEED_PATTERN = "Lease Deed"
ECHALLAN_PATTERN = "challan"

# ──────────────────────────────────────────────
# Supported Document Types
# ──────────────────────────────────────────────
DOCUMENT_TYPES = {
    "na_order": "NA (Non-Agricultural) Permission Order",
    "lease_deed": "Lease Deed Document",
    "echallan": "Electronic Challan",
}


def validate_config():
    """Validate that required configuration is present."""
    errors = []

    if not GEMINI_API_KEY:
        errors.append(
            "GEMINI_API_KEY not set. Copy .env.example to .env and add your key."
        )

    if not INPUT_DIR.exists():
        errors.append(f"Input directory not found: {INPUT_DIR}")

    if errors:
        raise ValueError(
            "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
        )


if __name__ == "__main__":
    # Quick config verification
    print(f"Base Directory  : {BASE_DIR}")
    print(f"Input Directory : {INPUT_DIR}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print(f"Audit DB Path   : {AUDIT_DB_PATH}")
    print(f"LLM Model       : {LLM_MODEL_NAME}")
    print(f"API Key Set     : {'Yes' if GEMINI_API_KEY else 'No'}")
