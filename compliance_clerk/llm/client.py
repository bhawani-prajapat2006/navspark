"""
LLM client wrapper for Google Gemini API.

Provides a reusable client with exponential backoff retry logic,
configurable model parameters, and structured error handling.
Uses the modern google-genai SDK.
"""

import time
import logging
from typing import Optional

from google import genai
from google.genai.types import GenerateContentConfig

from compliance_clerk.config import (
    GEMINI_API_KEY,
    LLM_MODEL_NAME,
    LLM_TEMPERATURE,
    LLM_MAX_RETRIES,
    LLM_RETRY_DELAY,
)

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Custom exception for LLM client errors."""
    pass


class LLMClient:
    """
    Wrapper around Google Gemini API with retry logic.

    Usage:
        client = LLMClient()
        response = client.generate("Extract data from this text...")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        """
        Initialize the LLM client.

        Args:
            api_key: Gemini API key (defaults to config).
            model_name: Model to use (defaults to config).
            temperature: Generation temperature (defaults to config).
        """
        self.api_key = api_key or GEMINI_API_KEY
        self.model_name = model_name or LLM_MODEL_NAME
        self.temperature = temperature if temperature is not None else LLM_TEMPERATURE

        if not self.api_key:
            raise LLMClientError(
                "Gemini API key not set. Copy .env.example to .env and add your key."
            )

        # Initialize the Gemini client
        self.client = genai.Client(api_key=self.api_key)

        logger.info(f"LLM client initialized with model: {self.model_name}")

    def generate(self, prompt: str, max_retries: Optional[int] = None) -> str:
        """
        Send a prompt to the LLM and return the response text.

        Implements exponential backoff retry on transient failures.

        Args:
            prompt: The text prompt to send to the LLM.
            max_retries: Override default max retries.

        Returns:
            The LLM's response text.

        Raises:
            LLMClientError: If all retry attempts fail.
        """
        retries = max_retries if max_retries is not None else LLM_MAX_RETRIES

        last_error = None
        for attempt in range(1, retries + 1):
            try:
                logger.info(f"LLM request attempt {attempt}/{retries}")

                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=GenerateContentConfig(
                        temperature=self.temperature,
                    ),
                )

                if response and response.text:
                    logger.info(
                        f"LLM response received ({len(response.text)} chars)"
                    )
                    return response.text
                else:
                    raise LLMClientError("Empty response from LLM")

            except LLMClientError:
                raise  # Don't retry on empty responses

            except Exception as e:
                last_error = e
                logger.warning(
                    f"LLM request failed (attempt {attempt}/{retries}): {e}"
                )

                if attempt < retries:
                    # Exponential backoff: 2s, 4s, 8s...
                    delay = LLM_RETRY_DELAY * (2 ** (attempt - 1))
                    logger.info(f"Retrying in {delay}s...")
                    time.sleep(delay)

        raise LLMClientError(
            f"All {retries} LLM attempts failed. Last error: {last_error}"
        )


if __name__ == "__main__":
    """Quick test of the LLM client."""
    logging.basicConfig(level=logging.INFO)

    try:
        client = LLMClient()
        response = client.generate("Say 'Hello from Compliance Clerk!' in one line.")
        print(f"LLM Response: {response}")
    except LLMClientError as e:
        print(f"Error: {e}")
