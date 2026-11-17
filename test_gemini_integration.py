import json
import os
import sys
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Import the function to test
from gemini_service import extract_medical_data_with_gemini, GeminiServiceError

# Prepare a short fictional medical report text
sample_text = """Patient Name: John Doe
Report Date: 2026-10-30
Diagnosis: Hypertension
Lab Test: Blood Pressure - 140/90 mmHg
Medication: Lisinopril 10mg once daily
Doctor: Dr. Jane Smith
Hospital: City Health Center"""

# Expected JSON output matching MedicalReportSchema
expected_json = {
    "patient_name": "John Doe",
    "report_date": "2026-10-30",
    "diagnosis": "Hypertension",
    "tests": [{"test_name": "Blood Pressure", "value": "140/90", "unit": "mmHg"}],
    "medications": [{"name": "Lisinopril", "dosage": "10mg", "frequency": "once daily"}],
    "doctor_name": "Dr. Jane Smith",
    "hospital_name": "City Health Center",
}

# Mock client and response
mock_response = MagicMock()
mock_response.text = json.dumps(expected_json)

mock_model = MagicMock()
mock_model.generate_content.return_value = mock_response

mock_models = MagicMock()
mock_models.generate_content = mock_model.generate_content


mock_client = MagicMock()
mock_client.models = mock_model


# Patch the get_gemini_client function to return our mock client
with patch('gemini_service.get_gemini_client', return_value=mock_client):
    # Also patch environment variable for model name to ensure new default works
    os.environ['GEMINI_MODEL'] = 'gemini-3.8-flash'
    try:
        result = extract_medical_data_with_gemini(sample_text)
        print('Extraction succeeded')
        print(json.dumps(result, indent=2))
    except GeminiServiceError as e:
        print('GeminiServiceError:', e)
