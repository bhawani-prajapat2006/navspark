"""
Demo/cached responses for testing without API access.

Pre-built LLM responses based on actual PDF content,
allowing the pipeline to be tested and demonstrated
when the Gemini API quota is unavailable.
"""

import re
import logging

logger = logging.getLogger(__name__)

# Pre-extracted data keyed by (survey_number, doc_type)
DEMO_NA_ORDERS = {
    "251": '{"survey_number": "251/p2", "village": "Rampura Mota", "area_in_na_order": 5997.0, "dated": "16/02/2026", "na_order_number": "iORA/31/02/112/25/2026"}',
    "255": '{"survey_number": "255", "village": "Rampura Mota", "area_in_na_order": 16534.0, "dated": "07/01/2026", "na_order_number": "iORA/31/02/112/7/2026"}',
    "256": '{"survey_number": "256", "village": "Rampura Mota", "area_in_na_order": 5997.0, "dated": "21/01/2026", "na_order_number": "iORA/31/02/112/9/2026"}',
    "257": '{"survey_number": "257", "village": "Rampura Mota", "area_in_na_order": 16534.0, "dated": "07/01/2026", "na_order_number": "iORA/31/02/112/7/2026"}',
}

DEMO_LEASE_DEEDS = {
    "251": '{"survey_number": "251/p2", "lease_deed_doc_number": "1141/2026", "lease_area": 5997.0, "lease_start_date": "21/01/2026"}',
    "255": '{"survey_number": "255", "lease_deed_doc_number": "838/2025", "lease_area": 16792.0, "lease_start_date": "28/05/2025"}',
    "256": '{"survey_number": "256", "lease_deed_doc_number": "854/2025", "lease_area": 5997.0, "lease_start_date": "28/05/2025"}',
    "257": '{"survey_number": "257", "lease_deed_doc_number": "837/2025", "lease_area": 16792.0, "lease_start_date": "28/05/2025"}',
}


class DemoLLMClient:
    """
    Mock LLM client that returns pre-built responses.
    Used when Gemini API quota is unavailable (--demo mode).
    Matches responses by detecting document type and survey number in the prompt.
    """

    def __init__(self, **kwargs):
        """Accept any kwargs (matches LLMClient interface)."""
        pass

    def generate(self, prompt: str, max_retries=None) -> str:
        """Return cached response by detecting doc type and survey number."""
        # Detect document type from prompt
        is_lease = "lease" in prompt.lower() or "lease_deed" in prompt.lower()

        # Extract survey number from prompt (look for 3-digit numbers)
        survey_nums = re.findall(r'\b(25[1567])\b', prompt)

        if survey_nums:
            survey_key = survey_nums[0]
            if is_lease and survey_key in DEMO_LEASE_DEEDS:
                logger.info(f"[DEMO] Returning cached lease deed for survey {survey_key}")
                return DEMO_LEASE_DEEDS[survey_key]
            elif survey_key in DEMO_NA_ORDERS:
                logger.info(f"[DEMO] Returning cached NA order for survey {survey_key}")
                return DEMO_NA_ORDERS[survey_key]

        # Fallback
        logger.warning(f"[DEMO] No cached response found, returning fallback")
        return '{"survey_number": "unknown", "village": "unknown", "area_in_na_order": 0.0, "dated": "", "na_order_number": ""}'
