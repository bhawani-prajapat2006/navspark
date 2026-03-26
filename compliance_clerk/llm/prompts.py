"""
LLM prompt templates for document data extraction.

Contains carefully crafted prompts that instruct the LLM to extract
specific fields from each document type and return valid JSON.
Each prompt includes the exact JSON schema and extraction rules.
"""


def build_na_order_prompt(text: str) -> str:
    """
    Build a prompt to extract NA Order fields from PDF text.

    The prompt instructs the LLM to find:
    - Survey Number, Village, Area, Date, Order Number

    Args:
        text: Extracted text from the NA Order PDF.

    Returns:
        Formatted prompt string.
    """
    return f"""You are a document data extraction specialist. Extract the following fields 
from this NA (Non-Agricultural) Permission Order document.

The document is in Gujarati language with some English text mixed in. 
Focus on finding these specific data points:

1. **survey_number**: The land survey/block number (e.g., "257", "251/p2", "255"). 
   Look for patterns like "સર્વે/બ્લોક નં" or numbers before "FINAL ORDER" in the filename context.

2. **village**: The village name where the land is located (e.g., "Rampura Mota", "રામપુરા મોટા").
   Look for "ગામ", "મૌજે" or village references. Convert Gujarati village names to English.

3. **area_in_na_order**: The land area in square meters. 
   Look for numbers followed by "ચો.મી." or "sq.m" or "ચોરસ મીટર".
   Return as a number (float), not a string.

4. **dated**: The date of the NA order. 
   Look for dates near "તા." or "dated" or at the top of the document. 
   Return in DD/MM/YYYY format.

5. **na_order_number**: The official order number.
   Look for "હુકમ નં." or "iORA/" pattern (e.g., "iORA/31/02/112/7/2026").

IMPORTANT RULES:
- Return ONLY valid JSON, no other text or markdown.
- Do NOT wrap the response in ```json``` code blocks.
- If a field cannot be found, use reasonable defaults: empty string "" for text, 0.0 for numbers.
- The area should be the total area mentioned in the NA order permission.

Expected JSON format:
{{
    "survey_number": "255",
    "village": "Rampura Mota",
    "area_in_na_order": 16534.0,
    "dated": "7/1/2026",
    "na_order_number": "iORA/31/02/112/7/2026"
}}

--- DOCUMENT TEXT ---
{text}
--- END DOCUMENT ---

Extract the fields and return ONLY the JSON object:"""


def build_lease_deed_prompt(text: str) -> str:
    """
    Build a prompt to extract Lease Deed fields from PDF text.

    The prompt instructs the LLM to find:
    - Survey Number, Document Number, Lease Area, Lease Start Date

    Args:
        text: Extracted text from the Lease Deed PDF.

    Returns:
        Formatted prompt string.
    """
    return f"""You are a document data extraction specialist. Extract the following fields
from this Lease Deed document.

The document may be in Gujarati and/or English. Focus on finding these specific data points:

1. **survey_number**: The land survey/block number referenced in the deed.
   Look for "સર્વે નં", "S.No.", or survey references.

2. **lease_deed_doc_number**: The lease deed document/registration number.
   Look for "Doc No.", "દસ્તાવેજ નં", registration numbers, or "Lease Deed No.".
   This is typically a number like "837/2025" or "838".

3. **lease_area**: The leased area in square meters.
   Look for area measurements with "ચો.મી.", "sq.m", or "square meters".
   Return as a number (float), not a string.

4. **lease_start_date**: The start date of the lease agreement.
   Look for "Lease Start", "લીઝ શરૂ", execution date, or the date the deed was executed.
   Return in DD/MM/YYYY format.

IMPORTANT RULES:
- Return ONLY valid JSON, no other text or markdown.
- Do NOT wrap the response in ```json``` code blocks.
- If a field cannot be found, use reasonable defaults: empty string "" for text, 0.0 for numbers.

Expected JSON format:
{{
    "survey_number": "255",
    "lease_deed_doc_number": "837/2025",
    "lease_area": 16792.0,
    "lease_start_date": "28/05/2025"
}}

--- DOCUMENT TEXT ---
{text}
--- END DOCUMENT ---

Extract the fields and return ONLY the JSON object:"""


def build_echallan_prompt(text: str) -> str:
    """
    Build a prompt to extract eChallan fields from PDF text.

    The prompt instructs the LLM to find:
    - Challan Number, Vehicle Number, Violation Date, Amount,
      Offence Description, Payment Status

    Args:
        text: Extracted text from the eChallan PDF.

    Returns:
        Formatted prompt string.
    """
    return f"""You are a document data extraction specialist. Extract the following fields
from this eChallan (electronic traffic challan) document.

1. **challan_number**: The unique challan/ticket number.
2. **vehicle_number**: The vehicle registration number (e.g., "GJ 01 AB 1234").
3. **violation_date**: Date of the traffic violation in DD/MM/YYYY format.
4. **amount**: The fine/penalty amount in INR. Return as a number (float).
5. **offence_description**: Brief description of the traffic offence.
6. **payment_status**: Current payment status ("Paid", "Unpaid", or "Pending").

IMPORTANT RULES:
- Return ONLY valid JSON, no other text or markdown.
- Do NOT wrap the response in ```json``` code blocks.
- If a field cannot be found, use reasonable defaults.

Expected JSON format:
{{
    "challan_number": "CH123456",
    "vehicle_number": "GJ 01 AB 1234",
    "violation_date": "15/03/2026",
    "amount": 500.0,
    "offence_description": "Signal jumping",
    "payment_status": "Unpaid"
}}

--- DOCUMENT TEXT ---
{text}
--- END DOCUMENT ---

Extract the fields and return ONLY the JSON object:"""


# Map document types to their prompt builders
PROMPT_MAP = {
    "na_order": build_na_order_prompt,
    "lease_deed": build_lease_deed_prompt,
    "echallan": build_echallan_prompt,
}
