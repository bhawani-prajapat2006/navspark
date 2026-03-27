"""
LLM client wrapper for Google Gemini API.

Uses direct REST API calls with multimodal support to send
PDF files as inline data, enabling Gemini's vision capabilities
to read scanned documents and CID-encoded fonts.
"""

import re
import time
import json
import base64
import logging
from pathlib import Path
from typing import Optional

import requests

from compliance_clerk.config import (
    GEMINI_API_KEY,
    LLM_MODEL_NAME,
    LLM_TEMPERATURE,
    LLM_MAX_RETRIES,
)

logger = logging.getLogger(__name__)

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLMClientError(Exception):
    """Custom exception for LLM client errors."""
    pass


class LLMClient:
    """
    Wrapper around Google Gemini REST API with multimodal + rate-limit-aware retry.

    Supports sending PDF files directly to Gemini's vision API,
    bypassing broken text extraction for scanned/CID-encoded PDFs.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        self.api_key = api_key or GEMINI_API_KEY
        self.model_name = model_name or LLM_MODEL_NAME
        self.temperature = temperature if temperature is not None else LLM_TEMPERATURE

        if not self.api_key:
            raise LLMClientError(
                "Gemini API key not set. Copy .env.example to .env and add your key."
            )

        self.url = API_URL.format(model=self.model_name)
        logger.info(f"LLM client initialized with model: {self.model_name}")

    def _parse_retry_delay(self, error_data: dict) -> int:
        """Extract retry delay from API error response."""
        try:
            details = error_data.get("error", {}).get("details", [])
            for detail in details:
                if detail.get("@type", "").endswith("RetryInfo"):
                    delay_str = detail.get("retryDelay", "60s")
                    match = re.search(r"(\d+)", delay_str)
                    if match:
                        return int(match.group(1)) + 5
        except Exception:
            pass
        return 65

    def _make_request(self, payload: dict, retries: int) -> str:
        """Make API request with retry logic. Returns response text."""
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                logger.info(f"LLM request attempt {attempt}/{retries}")

                response = requests.post(
                    f"{self.url}?key={self.api_key}",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=120,
                )

                if response.status_code == 200:
                    data = response.json()
                    text = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                    )
                    if text:
                        logger.info(f"LLM response received ({len(text)} chars)")
                        return text
                    else:
                        raise LLMClientError("Empty response from LLM")

                elif response.status_code == 429:
                    error_data = response.json()
                    delay = self._parse_retry_delay(error_data)
                    last_error = Exception("429 Rate Limited")
                    logger.warning(
                        f"Rate limited (attempt {attempt}/{retries}). "
                        f"Waiting {delay}s for quota to reset..."
                    )
                    if attempt < retries:
                        time.sleep(delay)
                    continue

                else:
                    error_msg = response.text[:200]
                    last_error = Exception(f"HTTP {response.status_code}: {error_msg}")
                    logger.error(f"API error (attempt {attempt}/{retries}): {error_msg}")
                    if attempt < retries:
                        time.sleep(10)

            except requests.exceptions.Timeout:
                last_error = Exception("Request timed out")
                logger.warning(f"Timeout (attempt {attempt}/{retries})")
                if attempt < retries:
                    time.sleep(10)

            except LLMClientError:
                raise

            except Exception as e:
                last_error = e
                logger.warning(f"Request failed (attempt {attempt}/{retries}): {e}")
                if attempt < retries:
                    time.sleep(10)

        raise LLMClientError(
            f"All {retries} LLM attempts failed. Last error: {last_error}"
        )

    def generate(self, prompt: str, max_retries: Optional[int] = None) -> str:
        """
        Send a text-only prompt to the LLM. Used for retry prompts.
        """
        retries = max_retries if max_retries is not None else LLM_MAX_RETRIES
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": self.temperature},
        }
        return self._make_request(payload, retries)

    def generate_with_pdf(
        self, prompt: str, pdf_path: str, max_retries: Optional[int] = None
    ) -> str:
        """
        Send a prompt with a PDF file to the LLM using Gemini's multimodal API.

        This enables Gemini to:
        - Read scanned/image-based PDFs directly
        - Handle CID-encoded fonts that pdfplumber can't extract
        - See the actual document layout for better extraction

        Args:
            prompt: Extraction instructions.
            pdf_path: Path to the PDF file.
            max_retries: Override for retry count.

        Returns:
            LLM response text.
        """
        retries = max_retries if max_retries is not None else LLM_MAX_RETRIES

        # Read and base64-encode the PDF
        pdf_data = Path(pdf_path).read_bytes()
        b64_data = base64.b64encode(pdf_data).decode("utf-8")

        logger.info(f"Sending PDF to LLM: {Path(pdf_path).name} ({len(pdf_data)} bytes)")

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "application/pdf",
                                "data": b64_data,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {"temperature": self.temperature},
        }

        return self._make_request(payload, retries)


if __name__ == "__main__":
    """Quick test of the LLM client."""
    logging.basicConfig(level=logging.INFO)

    try:
        client = LLMClient()
        response = client.generate("Say 'Hello from Compliance Clerk!' in one line.")
        print(f"LLM Response: {response}")
    except LLMClientError as e:
        print(f"Error: {e}")
