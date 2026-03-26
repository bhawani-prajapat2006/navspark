# The Compliance Clerk 🏛️

> Intelligent Document Extraction Pipeline for NA Orders & Lease Deeds

## Overview

An LLM-powered Python tool that automates the extraction of key data points from
heterogeneous PDF documents (NA Permission Orders and Lease Deed documents) and
consolidates them into a standardized Excel/CSV report.

## Features

- **Multi-Format PDF Parsing** — Handles NA Order and Lease Deed documents
- **LLM-Powered Extraction** — Uses Google Gemini to intelligently parse document text
- **Schema Enforcement** — Pydantic models ensure valid, structured output
- **Audit Trail** — All LLM interactions logged to SQLite for debugging
- **Excel/CSV Reports** — Standardized output matching expected format

## Project Structure

```
navspark/
├── compliance_clerk/       # Core package
│   ├── parsers/            # PDF text extraction
│   ├── models/             # Pydantic data schemas
│   ├── llm/                # LLM client, prompts, schema enforcement
│   ├── audit/              # SQLite audit logging
│   ├── pipeline/           # Extraction orchestration
│   └── output/             # Report generation (Excel/CSV)
├── data/
│   ├── input/              # Place PDF files here
│   └── output/             # Generated reports
├── tests/                  # Unit tests
├── main.py                 # CLI entry point
└── requirements.txt        # Dependencies
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up your API key
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# 3. Place PDF files in data/input/

# 4. Run the pipeline
python main.py --input-dir data/input/ --output-file data/output/output.xlsx
```

## Document Types Supported

| Document Type | Fields Extracted |
|---|---|
| NA Order | Survey No., Village, Area, Date, Order No. |
| Lease Deed | Survey No., Doc No., Lease Area, Lease Start Date |

## License

MIT
