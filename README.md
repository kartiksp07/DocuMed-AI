# DocuMed AI 📋🩺

**DocuMed AI** is a lightweight, beginner-friendly medical PDF-to-JSON extractor built with Python, Flask, `pypdf`, Google Gemini (`google-genai`), and SQLite. It provides an end-to-end pipeline that extracts unstructured text from clinical documents, validates and normalizes findings into structured JSON conforming to strict Pydantic schemas, and stores verified records in an embedded SQLite database.

> **Disclaimer:** DocuMed AI is an academic demonstration and student portfolio project. It is **not** a certified medical device, diagnostic system, or clinical decision support tool. It must never be used for real patient diagnosis or treatment decisions.

---

## 🌟 Key Features

- **Text-Based PDF Extraction**: Extracts clinical text across multi-page PDF documents using `pypdf` with edge-case handling (empty files, password protection, corrupted files, and non-extractable documents).
- **Automated Ephemeral Cleanup**: Automatically deletes temporary uploaded PDF files immediately after text extraction to protect privacy and prevent server storage bloat.
- **Structured AI Normalization**: Uses Google Gemini (`gemini-2.5-flash`) via the official `google-genai` SDK with strict JSON schema constraints.
- **Strict Pydantic Validation**: Ensures output adheres to structured schemas covering patient demographics, report date, diagnostic findings, lab tests (test name, observed value, unit), and prescribed medications (name, dosage, frequency).
- **Anti-Hallucination Guarantees**: Enforces rules that absent data must evaluate to `null` or `[]`—never hallucinated or invented.
- **Embedded SQLite Persistence**: Automatically initializes and manages `instance/documed.db` using parameterized queries and context-managed connections.
- **Interactive UI**: Responsive Flask + vanilla HTML/CSS dashboard with drag-and-drop file staging, recent reports history, report details viewer, and a one-click JSON copy utility.

---

## 🏗️ System Architecture

```text
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  Uploaded PDF   │ ───►  │ pypdf Extractor │ ───►  │ Google Gemini   │
│ (Max size 16MB) │       │ (Text Parsing)  │       │ (Structured AI) │
└─────────────────┘       └────────┬────────┘       └────────┬────────┘
                                   │                         │
                                   ▼                         ▼
                          ┌─────────────────┐       ┌─────────────────┐
                          │ Automatic File  │       │    Pydantic     │
                          │ Disk Cleanup    │       │ Schema Validate │
                          └─────────────────┘       └────────┬────────┘
                                                             │
                                                             ▼
                                                    ┌─────────────────┐
                                                    │ SQLite Storage  │
                                                    │ (instance/*.db) │
                                                    └─────────────────┘
```

---

## 📁 Project Structure

```text
DocuMedAi/
├── app.py                 # Main Flask application & routes (/, /report/<id>)
├── pdf_extractor.py       # PDF parsing & text extraction via pypdf
├── gemini_service.py      # Google GenAI service with structured schema enforcement
├── schemas.py             # Pydantic data models for medical report validation
├── database.py            # SQLite helper with parameterized queries & connection manager
├── requirements.txt       # Project dependencies (Flask, pypdf, google-genai, pydantic)
├── .env                   # Local environment variables & API key (Git-ignored)
├── .env.example           # Example environment template for repository users
├── .gitignore             # Excludes secrets, uploads, *.pdf, *.db, and virtual environments
├── sample_medical_report.pdf # Ready-to-test sample clinical summary
├── README.md              # Project documentation and quickstart guide
├── templates/
│   └── index.html         # Responsive web dashboard & report viewer
├── static/
│   └── style.css          # Medical-tech UI stylesheet
└── instance/
    └── documed.db         # Auto-generated SQLite database (Git-ignored)
```

---

## 📋 Supported PDFs & Limitations

- **Supported Documents**: Standard text-based PDF documents (clinical consultation notes, discharge summaries, laboratory panels with selectable text).
- **Limitations**:
  - **Scanned Images**: PDFs containing only scanned bitmaps/images without embedded text streams are detected and rejected (OCR is not implemented in this lightweight version).
  - **Encrypted / Password-Protected**: Documents requiring a non-empty password to view will produce a user-facing error message.
  - **File Size**: Maximum upload size is strictly limited to **16 MB**.

---

## 🚀 Setup & Local Installation

### 1. Prerequisites
- **Python 3.10+** (Python 3.13 recommended).
- A free Google Gemini API key from [Google AI Studio](https://aistudio.google.com/).

### 2. Clone or Open the Project
Open Windows PowerShell inside the project directory:
```powershell
cd c:\Users\karti\Desktop\DocuMedAi
```

### 3. Create & Activate Virtual Environment

```powershell
# Create virtual environment using the Python 3 launcher
py -3 -m venv venv

# Activate on Windows PowerShell
.\venv\Scripts\Activate.ps1

# (If using macOS / Linux)
# python3 -m venv venv
# source venv/bin/activate
```

> *If PowerShell restricts script execution, run:*
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> .\venv\Scripts\Activate.ps1
> ```

### 4. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 5. Configure Environment Variables

Create your local `.env` file by copying the example:
```powershell
Copy-Item .env.example .env
```

Open `.env` and insert your Gemini API key:
```env
FLASK_APP=app.py
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=replace-with-a-secure-secret-key

# Get your key at: https://aistudio.google.com/
GEMINI_API_KEY=AIzaSy...your_actual_key_here
GEMINI_MODEL=gemini-2.5-flash
```

---

## 🏃 Running the Application

Start the Flask development server:
```powershell
python app.py
```

Open your browser and navigate to:
```text
http://127.0.0.1:5000
```

1. Drag and drop or browse for `sample_medical_report.pdf` (located in the project root).
2. Click **Upload, Extract & Save Report**.
3. View the extracted text, demographic summary, laboratory tests table, medications table, and formatted JSON output.
4. Scroll down to **Recent Stored Reports** and click **View Report** to retrieve any previously saved record from SQLite.

---

## 🧪 Testing Instructions

The project includes unit and integration tests covering extraction, AI validation, and database persistence.

To execute all tests:
```powershell
# Run PDF extractor test suite
python -m unittest scratch/test_extractor.py

# Or run the integrated test suite directly
python -c "
import sys; sys.path.insert(0, '.');
from pdf_extractor import extract_text_from_pdf;
print('Extracted:', len(extract_text_from_pdf('sample_medical_report.pdf')), 'chars')
"
```

---

## 📄 Sample JSON Output (Fictional Data)

Below is an example of the structured JSON generated and validated against `MedicalReportSchema`:

```json
{
  "patient_name": "Jane Smith",
  "report_date": "October 28, 2026",
  "diagnosis": "Type 2 Diabetes Mellitus & Essential Hypertension",
  "tests": [
    {
      "test_name": "Fasting Blood Glucose",
      "value": "138",
      "unit": "mg/dL"
    },
    {
      "test_name": "HbA1c",
      "value": "7.2",
      "unit": "%"
    },
    {
      "test_name": "Total Cholesterol",
      "value": "215",
      "unit": "mg/dL"
    },
    {
      "test_name": "Serum Creatinine",
      "value": "0.9",
      "unit": "mg/dL"
    }
  ],
  "medications": [
    {
      "name": "Metformin",
      "dosage": "500mg",
      "frequency": "Twice daily with meals"
    },
    {
      "name": "Lisinopril",
      "dosage": "10mg",
      "frequency": "Once daily in morning"
    }
  ],
  "doctor_name": "Dr. Sarah Johnson, MD",
  "hospital_name": "DOCUMED MEDICAL CENTER"
}
```

---

## 🔒 Security & Privacy Notes

- **Git Exclusion**: `.env`, SQLite database files (`*.db`), virtual environments (`venv/`), and uploaded files (`uploads/`) are excluded from version control via `.gitignore`.
- **Injection Prevention**: All SQLite queries utilize parameterized placeholders (`?`).
- **File Sanitization**: Upload filenames are sanitized with `werkzeug.utils.secure_filename`, and files are unlinked from disk upon processing completion.
