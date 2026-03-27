"""
Audit trail logging for LLM interactions.

Stores all LLM prompts, responses, and validation results in a
SQLite database for debugging, quality auditing, and compliance.
"""

import json
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from compliance_clerk.config import AUDIT_DB_PATH

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    SQLite-based audit logger for tracking all LLM extractions.

    Each extraction attempt is logged with:
    - Timestamp, document info, prompt, raw response
    - Parsed JSON result, validation status, error details

    Usage:
        audit = AuditLogger()
        audit.log_extraction(
            document_name="255 FINAL ORDER.pdf",
            document_type="na_order",
            prompt="...",
            raw_response="...",
            parsed_json={"survey_number": "255", ...},
            status="success"
        )
    """

    def __init__(self, db_path: Optional[str | Path] = None):
        """
        Initialize the audit logger and create the table if needed.

        Args:
            db_path: Path to the SQLite database. Defaults to config.
        """
        self.db_path = str(db_path or AUDIT_DB_PATH)
        self._init_db()
        logger.info(f"Audit logger initialized: {self.db_path}")

    def _init_db(self):
        """Create the audit_logs table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    document_name TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    raw_response TEXT,
                    parsed_json TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    attempt_number INTEGER DEFAULT 1
                )
            """)
            conn.commit()

    def log_extraction(
        self,
        document_name: str,
        document_type: str,
        prompt: str,
        raw_response: str = "",
        parsed_json: Optional[dict] = None,
        status: str = "success",
        error_message: str = "",
        attempt_number: int = 1,
    ):
        """
        Log a single extraction attempt to the database.

        Args:
            document_name: Name of the PDF file processed.
            document_type: Type of document (na_order, lease_deed, echallan).
            prompt: The full prompt sent to the LLM.
            raw_response: The raw text response from the LLM.
            parsed_json: The validated JSON data (if successful).
            status: Result status ('success', 'validation_error', 'llm_error').
            error_message: Error description (if failed).
            attempt_number: Which retry attempt this was.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        json_str = json.dumps(parsed_json) if parsed_json else None

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO audit_logs 
                    (timestamp, document_name, document_type, prompt, 
                     raw_response, parsed_json, status, error_message, attempt_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    document_name,
                    document_type,
                    prompt,
                    raw_response,
                    json_str,
                    status,
                    error_message,
                    attempt_number,
                ),
            )
            conn.commit()

        logger.info(
            f"Audit logged: {document_name} ({document_type}) - {status}"
        )

    def get_logs(self, limit: int = 50, status_filter: Optional[str] = None) -> list[dict]:
        """
        Retrieve audit logs from the database.

        Args:
            limit: Maximum number of records to return.
            status_filter: Optional filter by status (e.g., 'success', 'error').

        Returns:
            List of audit log entries as dictionaries.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if status_filter:
                cursor = conn.execute(
                    "SELECT * FROM audit_logs WHERE status = ? ORDER BY id DESC LIMIT ?",
                    (status_filter, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?",
                    (limit,),
                )

            return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> dict:
        """
        Get summary statistics of all audit logs.

        Returns:
            Dict with total count, success count, error count.
        """
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
            success = conn.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE status = 'success'"
            ).fetchone()[0]
            errors = conn.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE status != 'success'"
            ).fetchone()[0]

        return {
            "total_extractions": total,
            "successful": success,
            "failed": errors,
        }

    def get_processed_documents(self) -> set:
        """
        Get the set of document names that have been successfully processed.
        Used by incremental mode to skip already-extracted documents.

        Returns:
            Set of document filenames with successful extractions.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT DISTINCT document_name FROM audit_logs WHERE status = 'success'"
            )
            return {row[0] for row in cursor.fetchall()}

    def get_cached_results(self, document_name: str, document_type: str) -> Optional[dict]:
        """
        Retrieve the most recent successful extraction result for a document.

        Args:
            document_name: Name of the PDF file.
            document_type: Type (na_order, lease_deed, echallan).

        Returns:
            Parsed JSON dict if found, None otherwise.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """SELECT parsed_json FROM audit_logs
                   WHERE document_name = ? AND document_type = ? AND status = 'success'
                   ORDER BY id DESC LIMIT 1""",
                (document_name, document_type),
            )
            row = cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
        return None

    def export_to_jsonl(self, output_path: str | Path) -> int:
        """
        Export all audit logs to a JSONL file.

        Args:
            output_path: Path for the output JSONL file.

        Returns:
            Number of records exported.
        """
        logs = self.get_logs(limit=10000)
        output_path = Path(output_path)

        with open(output_path, "w") as f:
            for log in logs:
                f.write(json.dumps(log) + "\n")

        logger.info(f"Exported {len(logs)} audit logs to {output_path}")
        return len(logs)


if __name__ == "__main__":
    """Quick test of audit logging."""
    import tempfile
    import os

    # Use a temp DB for testing
    test_db = tempfile.mktemp(suffix=".db")

    try:
        audit = AuditLogger(db_path=test_db)

        # Log a successful extraction
        audit.log_extraction(
            document_name="255 FINAL ORDER.pdf",
            document_type="na_order",
            prompt="Extract fields from...",
            raw_response='{"survey_number": "255"}',
            parsed_json={"survey_number": "255", "village": "Rampura Mota"},
            status="success",
        )

        # Log a failed extraction
        audit.log_extraction(
            document_name="bad_file.pdf",
            document_type="na_order",
            prompt="Extract fields from...",
            raw_response="Sorry, I could not parse this.",
            status="validation_error",
            error_message="No JSON found in response",
        )

        # Check stats
        stats = audit.get_stats()
        print(f"Stats: {stats}")
        assert stats["total_extractions"] == 2
        assert stats["successful"] == 1
        assert stats["failed"] == 1

        # Check logs retrieval
        logs = audit.get_logs()
        assert len(logs) == 2
        print(f"Logs retrieved: {len(logs)} entries")

        # Test JSONL export
        jsonl_path = tempfile.mktemp(suffix=".jsonl")
        count = audit.export_to_jsonl(jsonl_path)
        print(f"Exported: {count} records to JSONL")
        os.unlink(jsonl_path)

        print("\nAll audit logger tests passed! ✓")

    finally:
        os.unlink(test_db)
