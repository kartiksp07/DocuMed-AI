import os
import json
from gemini_service import extract_medical_data_with_gemini, GeminiServiceError

# Short fictional medical report
sample_text = """Patient Name: Alice Example
Report Date: 2026-11-01
Diagnosis: Seasonal Allergies
Lab Test: IgE - 150 IU/mL
Medication: Cetirizine 10mg once daily
Doctor: Dr. Emily White
Hospital: Example Medical Center"""

try:
    result = extract_medical_data_with_gemini(sample_text)
    print('REAL Gemini API CALL SUCCESS')
    print(json.dumps(result, indent=2))
except GeminiServiceError as e:
    print('REAL Gemini API CALL FAILED')
    print(str(e))
