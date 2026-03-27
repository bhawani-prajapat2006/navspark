"""
The Compliance Clerk - CLI Entry Point

Command-line interface for running the document extraction pipeline.
Processes PDF documents from an input directory and generates
structured Excel/CSV reports.
"""

import argparse
import logging
import sys
from pathlib import Path

from compliance_clerk.config import INPUT_DIR, DEFAULT_OUTPUT_PATH, validate_config
from compliance_clerk.pipeline.extractor import ExtractionPipeline
from compliance_clerk.output.report_generator import generate_excel, generate_csv


def setup_logging(verbose: bool = False):
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="compliance-clerk",
        description=(
            "The Compliance Clerk - Intelligent Document Extraction\n"
            "Extracts data from NA Order and Lease Deed PDFs using LLM,\n"
            "and generates structured Excel/CSV reports."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--input-dir",
        type=str,
        default=str(INPUT_DIR),
        help=f"Directory containing PDF files (default: {INPUT_DIR})",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=str(DEFAULT_OUTPUT_PATH),
        help=f"Output file path (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--format",
        choices=["xlsx", "csv"],
        default="xlsx",
        help="Output format: xlsx or csv (default: xlsx)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose/debug logging",
    )
    parser.add_argument(
        "--export-audit",
        type=str,
        default=None,
        help="Export audit logs to JSONL file after processing",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run in demo mode using cached responses (no API key needed)",
    )

    return parser.parse_args()


def main():
    """Main entry point for the CLI."""
    args = parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger("compliance_clerk")
    logger.info("🏛️  The Compliance Clerk - Starting extraction pipeline")

    # Validate configuration (skip in demo mode)
    if not args.demo:
        try:
            validate_config()
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            sys.exit(1)

    # Initialize and run the pipeline
    try:
        if args.demo:
            from compliance_clerk.llm.demo_responses import DemoLLMClient
            logger.info("🔄 Running in DEMO mode (cached responses, no API calls)")
            pipeline = ExtractionPipeline(
                input_dir=args.input_dir,
                llm_client=DemoLLMClient(),
            )
        else:
            pipeline = ExtractionPipeline(input_dir=args.input_dir)
        rows = pipeline.run()
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        sys.exit(1)

    if not rows:
        logger.warning("No data extracted. Check your input files and logs.")
        sys.exit(0)

    # Generate report
    output_path = args.output_file
    if args.format == "csv":
        if not output_path.endswith(".csv"):
            output_path = str(Path(output_path).with_suffix(".csv"))
        report_path = generate_csv(rows, output_path)
    else:
        if not output_path.endswith(".xlsx"):
            output_path = str(Path(output_path).with_suffix(".xlsx"))
        report_path = generate_excel(rows, output_path)

    # Export audit logs if requested
    if args.export_audit:
        pipeline.audit_logger.export_to_jsonl(args.export_audit)
        logger.info(f"Audit logs exported to: {args.export_audit}")

    # Summary
    print("\n" + "=" * 50)
    print("📊 EXTRACTION COMPLETE")
    print("=" * 50)
    print(f"  Documents processed : {len(rows)} pairs")
    print(f"  Output file         : {report_path}")
    print(f"  Format              : {args.format.upper()}")

    stats = pipeline.audit_logger.get_stats()
    print(f"  LLM calls (total)   : {stats['total_extractions']}")
    print(f"  Successful          : {stats['successful']}")
    print(f"  Failed              : {stats['failed']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
