"""
test_app.py - Comprehensive Unit & Integration Test Suite for DocuMed AI

Runs automated tests for:
1. PDF Text Extraction & Edge Cases (empty, corrupted, encrypted, no-text)
2. Pydantic Schemas & Gemini Service Error Handling (validation, malformed JSON, API key sanitization)
3. SQLite Database Layer (table creation, parameterized queries, rejection of unvalidated data, persistence)
4. Flask Application Endpoints & Security (file cleanup, 413 handling, report viewer, non-PDF rejection)
"""

import io
import json
import os
import sqlite3
import sys
import unittest
from unittest.mock import patch

# Ensure project root is in sys.path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import pypdf
from pydantic import ValidationError
from pdf_extractor import extract_text_from_pdf, PDFExtractionError
from schemas import MedicalReportSchema, TestResult, Medication
from gemini_service import (
    GeminiServiceError,
    parse_and_validate_json,
    sanitize_error_message,
    get_gemini_client,
)
from database import (
    DATABASE_PATH,
    get_db_connection,
    init_db,
    save_medical_report,
    get_recent_reports,
    get_report_by_id,
    DatabaseError,
)
from app import app, is_allowed_file

FICTIONAL_REPORT_DATA = {
    "patient_name": "Jane Smith",
    "report_date": "October 28, 2026",
    "diagnosis": "Type 2 Diabetes Mellitus & Essential Hypertension",
    "tests": [
        {"test_name": "Fasting Blood Glucose", "value": "138", "unit": "mg/dL"},
        {"test_name": "HbA1c", "value": "7.2", "unit": "%"},
        {"test_name": "Total Cholesterol", "value": "215", "unit": "mg/dL"},
        {"test_name": "Serum Creatinine", "value": "0.9", "unit": "mg/dL"}
    ],
    "medications": [
        {"name": "Metformin", "dosage": "500mg", "frequency": "Twice daily with meals"},
        {"name": "Lisinopril", "dosage": "10mg", "frequency": "Once daily in morning"}
    ],
    "doctor_name": "Dr. Sarah Johnson, MD",
    "hospital_name": "DOCUMED MEDICAL CENTER"
}


class TestPDFExtraction(unittest.TestCase):
    """Tests for pdf_extractor.py"""

    def setUp(self):
        self.test_dir = os.path.join(BASE_DIR, "test_tmp")
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            for f in os.listdir(self.test_dir):
                try:
                    os.remove(os.path.join(self.test_dir, f))
                except OSError:
                    pass
            try:
                os.rmdir(self.test_dir)
            except OSError:
                pass

    def test_01_valid_pdf_extraction(self):
        """Extract text from sample_medical_report.pdf."""
        sample_path = os.path.join(BASE_DIR, "sample_medical_report.pdf")
        self.assertTrue(os.path.exists(sample_path), "sample_medical_report.pdf must exist")
        text = extract_text_from_pdf(sample_path)
        self.assertIn("Jane Smith", text)
        self.assertIn("Fasting Blood Glucose", text)
        self.assertIn("Metformin", text)

    def test_02_empty_zero_byte_file(self):
        """Empty 0-byte file must raise PDFExtractionError."""
        empty_path = os.path.join(self.test_dir, "empty.pdf")
        with open(empty_path, "wb") as f:
            pass
        with self.assertRaises(PDFExtractionError) as ctx:
            extract_text_from_pdf(empty_path)
        self.assertIn("empty", str(ctx.exception).lower())

    def test_03_corrupted_pdf_file(self):
        """Corrupted PDF header must raise PDFExtractionError."""
        corrupted_path = os.path.join(self.test_dir, "corrupt.pdf")
        with open(corrupted_path, "wb") as f:
            f.write(b"CORRUPTED_NOT_A_REAL_PDF_DATA")
        with self.assertRaises(PDFExtractionError) as ctx:
            extract_text_from_pdf(corrupted_path)
        self.assertTrue("corrupted" in str(ctx.exception).lower() or "invalid" in str(ctx.exception).lower())

    def test_04_blank_pdf_no_text(self):
        """PDF containing blank pages with no text must raise PDFExtractionError."""
        blank_path = os.path.join(self.test_dir, "blank.pdf")
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(blank_path, "wb") as f:
            writer.write(f)

        with self.assertRaises(PDFExtractionError) as ctx:
            extract_text_from_pdf(blank_path)
        self.assertIn("No extractable text found", str(ctx.exception))

    def test_05_password_protected_pdf(self):
        """Encrypted PDF with password must raise PDFExtractionError."""
        enc_path = os.path.join(self.test_dir, "protected.pdf")
        sample_path = os.path.join(BASE_DIR, "sample_medical_report.pdf")
        reader = pypdf.PdfReader(sample_path)
        writer = pypdf.PdfWriter()
        for p in reader.pages:
            writer.add_page(p)
        writer.encrypt("super_secret_password")
        with open(enc_path, "wb") as f:
            writer.write(f)

        with self.assertRaises(PDFExtractionError) as ctx:
            extract_text_from_pdf(enc_path)
        self.assertIn("password-protected", str(ctx.exception))


class TestSchemasAndGemini(unittest.TestCase):
    """Tests for schemas.py and gemini_service.py"""

    def test_06_pydantic_schema_valid(self):
        """Valid dictionary must validate successfully against MedicalReportSchema."""
        model = MedicalReportSchema.model_validate(FICTIONAL_REPORT_DATA)
        self.assertEqual(model.patient_name, "Jane Smith")
        self.assertEqual(len(model.tests), 4)
        self.assertEqual(len(model.medications), 2)
        self.assertEqual(model.tests[0].unit, "mg/dL")

    def test_07_never_invent_missing_info(self):
        """Missing fields must default strictly to None or empty lists."""
        empty_model = MedicalReportSchema.model_validate({})
        self.assertIsNone(empty_model.patient_name)
        self.assertIsNone(empty_model.report_date)
        self.assertIsNone(empty_model.diagnosis)
        self.assertEqual(empty_model.tests, [])
        self.assertEqual(empty_model.medications, [])

    def test_08_schema_validation_error(self):
        """Missing required test_name in tests list must fail validation."""
        invalid_data = {"tests": [{"value": "120", "unit": "mg/dL"}]}
        with self.assertRaises(ValidationError):
            MedicalReportSchema.model_validate(invalid_data)

    def test_09_gemini_missing_api_key(self):
        """Placeholder or empty API key must raise GeminiServiceError."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "your_gemini_api_key_here"}):
            with self.assertRaises(GeminiServiceError) as ctx:
                get_gemini_client()
            self.assertIn("not configured", str(ctx.exception))

    def test_10_malformed_json_handling(self):
        """Malformed JSON string must raise GeminiServiceError."""
        malformed = '{"patient_name": "Jane", "broken_json": }'
        with self.assertRaises(GeminiServiceError) as ctx:
            parse_and_validate_json(malformed)
        self.assertIn("Malformed JSON", str(ctx.exception))

    def test_11_api_key_redaction_in_errors(self):
        """Sensitive API key patterns must be sanitized in error messages."""
        leak_msg = "Google API call failed with key AIzaSyD3fakeAPIkey1234567890abcdef123"
        sanitized = sanitize_error_message(leak_msg)
        self.assertNotIn("AIzaSyD3fakeAPIkey1234567890abcdef123", sanitized)
        self.assertIn("[REDACTED_API_KEY]", sanitized)


class TestDatabaseStorage(unittest.TestCase):
    """Tests for database.py"""

    def setUp(self):
        init_db()

    def test_12_rejection_of_invalid_report_data(self):
        """Never save invalid, empty, or unvalidated data."""
        with self.assertRaises(DatabaseError):
            save_medical_report({})
        with self.assertRaises(DatabaseError):
            save_medical_report(None)

    def test_13_save_and_retrieve_report(self):
        """Parameterized insert and retrieval of medical report."""
        rep_id = save_medical_report(FICTIONAL_REPORT_DATA)
        self.assertIsInstance(rep_id, int)
        self.assertGreater(rep_id, 0)

        record = get_report_by_id(rep_id)
        self.assertIsNotNone(record)
        self.assertEqual(record["id"], rep_id)
        self.assertEqual(record["patient_name"], "Jane Smith")
        self.assertEqual(record["data"]["diagnosis"], FICTIONAL_REPORT_DATA["diagnosis"])

    def test_14_recent_reports_order(self):
        """Recent reports list returns records ordered by ID DESC."""
        id1 = save_medical_report({"patient_name": "Patient Alpha"})
        id2 = save_medical_report({"patient_name": "Patient Beta"})
        recent = get_recent_reports(limit=5)
        self.assertGreaterEqual(len(recent), 2)
        # Verify descending order
        ids = [r["id"] for r in recent]
        self.assertEqual(ids, sorted(ids, reverse=True))


class TestFlaskIntegrationAndSecurity(unittest.TestCase):
    """End-to-end Flask application workflow and security tests."""

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_15_get_homepage_renders_disclaimer_and_recent_reports(self):
        """Homepage must render 200 with demo disclaimer and upload form."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("DocuMed AI", html)
        self.assertIn("Educational Project Demo", html)
        self.assertIn("Recent Stored Reports", html)

    def test_16_disallow_non_pdf_upload(self):
        """Uploading non-PDF extension must be blocked with error flash."""
        data = {
            "pdf_file": (io.BytesIO(b"malicious executable or script"), "payload.exe")
        }
        resp = self.client.post("/", data=data, content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Invalid file format", resp.data.decode("utf-8"))

    def test_17_temporary_file_cleanup_after_processing(self):
        """Uploaded PDF must be automatically removed from disk after text extraction."""
        sample_path = os.path.join(BASE_DIR, "sample_medical_report.pdf")
        with open(sample_path, "rb") as f:
            pdf_bytes = f.read()

        filename = "temp_cleanup_test.pdf"
        uploaded_target = os.path.join(app.config["UPLOAD_FOLDER"], filename)

        data = {
            "pdf_file": (io.BytesIO(pdf_bytes), filename)
        }
        resp = self.client.post("/", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        # Verify disk cleanup: file must NOT remain in uploads folder
        self.assertFalse(os.path.exists(uploaded_target), "Uploaded file was not cleaned up from disk")

    def test_18_full_end_to_end_flow_with_simulated_gemini(self):
        """Complete workflow: Upload PDF -> Extract Text -> Gemini Parse -> Validate -> Save SQLite -> Render."""
        sample_path = os.path.join(BASE_DIR, "sample_medical_report.pdf")
        with open(sample_path, "rb") as f:
            pdf_bytes = f.read()

        with patch("app.extract_medical_data_with_gemini", return_value=FICTIONAL_REPORT_DATA):
            data = {"pdf_file": (io.BytesIO(pdf_bytes), "clinical_test.pdf")}
            resp = self.client.post("/", data=data, content_type="multipart/form-data")

        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("Report successfully validated and saved to database", html)
        self.assertIn("Structured Medical Findings", html)
        self.assertIn("Jane Smith", html)
        self.assertIn("Fasting Blood Glucose", html)
        self.assertIn("Metformin", html)
        self.assertIn("Normalized JSON Output", html)

    def test_19_view_stored_report_route(self):
        """GET /report/<id> renders stored report findings and JSON viewer."""
        rep_id = save_medical_report(FICTIONAL_REPORT_DATA)
        resp = self.client.get(f"/report/{rep_id}")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("Viewing Database Record", html)
        self.assertIn(f"#{rep_id}", html)
        self.assertIn("Jane Smith", html)
        self.assertIn("Type 2 Diabetes Mellitus", html)

    def test_20_view_nonexistent_report_redirects_with_error(self):
        """GET /report/999999 redirects gracefully with error flash."""
        resp = self.client.get("/report/999999", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("was not found in the database", resp.data.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
