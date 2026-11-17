"""
schemas.py - Data Models for DocuMed AI

This module defines Pydantic models used to structure and validate
medical data extracted from clinical documents by Google Gemini.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class TestResult(BaseModel):
    """Laboratory or diagnostic test observation with test name, value, and unit."""
    test_name: str = Field(
        ...,
        description="Name of the laboratory test, measurement, or panel (e.g., 'Fasting Blood Glucose', 'HbA1c', 'Hemoglobin')"
    )
    value: Optional[str] = Field(
        None,
        description="Observed numeric or qualitative test value (e.g., '138', '7.2', 'Normal', 'Negative'), or null if unstated"
    )
    unit: Optional[str] = Field(
        None,
        description="Standard measurement unit (e.g., 'mg/dL', '%', 'g/dL', 'mmol/L'), or null if unitless or not specified"
    )


class Medication(BaseModel):
    """Prescribed drug or medication details."""
    name: str = Field(
        ...,
        description="Name of the medication or drug (e.g., 'Metformin', 'Lisinopril')"
    )
    dosage: Optional[str] = Field(
        None,
        description="Strength or dosage amount (e.g., '500mg', '10mg', '1 tablet'), or null if not stated"
    )
    frequency: Optional[str] = Field(
        None,
        description="Directions or frequency schedule (e.g., 'twice daily after meals', 'once daily at bedtime'), or null if not stated"
    )


class MedicalReportSchema(BaseModel):
    """
    Complete structured schema for validated medical report extraction.
    Rule: Never invent information. Missing fields must be null or empty lists.
    """
    patient_name: Optional[str] = Field(
        None,
        description="Full name of the patient as stated in the document, or null if missing"
    )
    report_date: Optional[str] = Field(
        None,
        description="Date of consultation or report (e.g., '2026-10-28' or as written), or null if missing"
    )
    diagnosis: Optional[str] = Field(
        None,
        description="Primary clinical diagnosis or findings as stated in the document, or null if missing"
    )
    tests: List[TestResult] = Field(
        default_factory=list,
        description="List of laboratory or diagnostic test results containing test names, values, and units"
    )
    medications: List[Medication] = Field(
        default_factory=list,
        description="List of prescribed medications including names, dosages, and frequencies"
    )
    doctor_name: Optional[str] = Field(
        None,
        description="Treating physician or specialist name, or null if missing"
    )
    hospital_name: Optional[str] = Field(
        None,
        description="Clinic, hospital, or laboratory facility name, or null if missing"
    )
