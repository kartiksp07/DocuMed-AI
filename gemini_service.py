"""
gemini_service.py - Google Gemini AI Service for DocuMed AI

This module uses the official google-genai SDK to transform unstructured
medical PDF text into validated JSON data conforming to MedicalReportSchema.
"""

import json
import os
import re
from typing import Any, Dict
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import ValidationError

from schemas import MedicalReportSchema

# Ensure environment variables are loaded
load_dotenv()


class GeminiServiceError(Exception):
    """Custom exception raised when Gemini API processing or validation fails."""
    pass


SYSTEM_INSTRUCTION = (
    "You are an expert clinical data extraction assistant. "
    "Your objective is to extract structured medical details from the provided medical document text.\n\n"
    "CRITICAL RULES:\n"
    "1. Strict Fidelity: ONLY extract information explicitly stated in the document text.\n"
    "2. No Hallucinations: NEVER invent, assume, extrapolate, or guess any medical information.\n"
    "3. Missing Information: If any field (patient name, date, diagnosis, test, medication) is absent or unstated, "
    "set it to null (or an empty list [] for list fields). Never insert placeholder strings like 'Unknown' or 'N/A'.\n"
    "4. Test Results: For tests, extract test_name, value, and unit separately when present.\n"
    "5. Format: Return strictly valid JSON conforming to the requested schema."
)


def sanitize_error_message(message: str) -> str:
    """
    Sanitizes error messages to prevent exposing API keys or sensitive query details.
    """
    # Redact Google API key formats if reflected in error strings
    sanitized = re.sub(r"AIza[0-9A-Za-z\-_]{25,50}", "[REDACTED_API_KEY]", message)
    sanitized = re.sub(r"key=[^&\s]+", "key=[REDACTED]", sanitized)
    return sanitized


def get_gemini_client() -> genai.Client:
    """
    Initializes and returns the Google GenAI client using GEMINI_API_KEY from .env.

    Raises:
        GeminiServiceError: If GEMINI_API_KEY is missing or unconfigured.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if not api_key or api_key == "your_gemini_api_key_here":
        raise GeminiServiceError(
            "Gemini API key is not configured. "
            "Please set a valid GEMINI_API_KEY in your .env file."
        )

    return genai.Client(api_key=api_key)


def parse_and_validate_json(raw_json_str: str) -> Dict[str, Any]:
    """
    Parses a raw JSON string and validates it against MedicalReportSchema.

    Args:
        raw_json_str (str): Raw JSON text string.

    Returns:
        dict: Validated dictionary representation of the medical report.

    Raises:
        GeminiServiceError: If JSON is malformed or violates the Pydantic schema.
    """
    if not raw_json_str or not raw_json_str.strip():
        raise GeminiServiceError("Received an empty response from Gemini.")

    cleaned = raw_json_str.strip()

    # Strip markdown code fences if present
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    # Parse JSON
    try:
        data_dict = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise GeminiServiceError(f"Malformed JSON returned by Gemini: {str(e)}")

    if not isinstance(data_dict, dict):
        raise GeminiServiceError("Gemini response is not a valid JSON object.")

    # Validate against Pydantic schema (enforces never saving unvalidated data)
    try:
        validated_model = MedicalReportSchema.model_validate(data_dict)
    except ValidationError as e:
        # Format validation error messages cleanly without stack traces
        errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
        raise GeminiServiceError(f"Schema validation error: {'; '.join(errors)}")

    return validated_model.model_dump()


def extract_medical_data_with_gemini(raw_text: str) -> Dict[str, Any]:
    """
    Sends raw medical report text to Gemini to extract structured JSON.

    Args:
        raw_text (str): Unstructured text extracted from a medical PDF.

    Returns:
        dict: Parsed and validated medical report dictionary.

    Raises:
        GeminiServiceError: If API key is missing, API call fails,
                            response is malformed, or validation fails.
    """
    if not raw_text or not raw_text.strip():
        raise GeminiServiceError("Cannot extract medical data from empty text.")

    client = get_gemini_client()
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

    prompt = (
        "Extract all available clinical and laboratory information from the following "
        "medical document text into structured JSON matching the schema.\n\n"
        "--- BEGIN MEDICAL DOCUMENT ---\n"
        f"{raw_text}\n"
        "--- END MEDICAL DOCUMENT ---"
    )

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=MedicalReportSchema,
            ),
        )
    except Exception as e:
        err_msg = str(e)
        if "API_KEY_INVALID" in err_msg or "API key not valid" in err_msg:
            raise GeminiServiceError(
                "The configured GEMINI_API_KEY is invalid. Please check your key at Google AI Studio."
            )
        elif "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
            raise GeminiServiceError(
                "Gemini API rate limit or quota exceeded. Please try again later."
            )
        else:
            safe_err = sanitize_error_message(err_msg)
            raise GeminiServiceError(f"Gemini API request failed: {safe_err}")

    if not response or not response.text:
        raise GeminiServiceError("Gemini API returned an empty response.")

    return parse_and_validate_json(response.text)
