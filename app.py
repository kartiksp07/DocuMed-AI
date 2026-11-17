"""
app.py - Main Flask Application for DocuMed AI

A lightweight web app for uploading medical PDFs, extracting text,
parsing structured medical JSON using Google Gemini, and persisting records in SQLite.
"""

import json
import os
import time
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from pdf_extractor import extract_text_from_pdf, PDFExtractionError
from gemini_service import extract_medical_data_with_gemini, GeminiServiceError
from database import (
    init_db,
    save_medical_report,
    get_recent_reports,
    get_report_by_id,
    DatabaseError,
)

# Load environment variables from .env
load_dotenv()

# Initialize Flask application
app = Flask(__name__)

# Secret key for session security and flash messages
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "default-dev-secret-key")

# Upload configurations
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"pdf"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
# Limit maximum upload file size to 16MB
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize SQLite database schema
init_db()


def is_allowed_file(filename: str) -> bool:
    """Checks whether the uploaded file has an allowed .pdf extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handles uploads exceeding the 16MB limit gracefully."""
    flash("The uploaded file exceeds the 16MB maximum size limit.", "error")
    return redirect(url_for("upload_pdf"))


@app.route("/", methods=["GET", "POST"])
def upload_pdf():
    """
    Main route:
    - GET: Displays the medical PDF upload form and recent reports.
    - POST: Validates, extracts text, extracts structured JSON via Gemini,
            and persists the validated record into SQLite.
    """
    recent_reports = []
    try:
        recent_reports = get_recent_reports()
    except DatabaseError as e:
        flash(f"Database error loading recent reports: {str(e)}", "warning")

    if request.method == "POST":
        # Check if the post request has the file part
        if "pdf_file" not in request.files:
            flash("No file part detected in request.", "error")
            return redirect(request.url)

        file = request.files["pdf_file"]

        # Check if user submitted without selecting a file
        if file.filename == "":
            flash("Please select a PDF file before uploading.", "error")
            return redirect(request.url)

        # Validate that the file has a .pdf extension
        if file and is_allowed_file(file.filename):
            base_safe_name = secure_filename(file.filename)
            # Fallback if filename contains only illegal characters
            if not base_safe_name or base_safe_name == ".pdf":
                base_safe_name = f"upload_{int(time.time())}_{uuid.uuid4().hex[:6]}.pdf"

            save_path = os.path.join(app.config["UPLOAD_FOLDER"], base_safe_name)
            file.save(save_path)

            extracted_text = None

            # Step 1: Extract text from the uploaded PDF with guaranteed cleanup
            try:
                extracted_text = extract_text_from_pdf(save_path)
            except PDFExtractionError as pe:
                flash(f"PDF extraction error: {str(pe)}", "error")
                return render_template(
                    "index.html",
                    uploaded_file=base_safe_name,
                    recent_reports=recent_reports,
                )
            except Exception as e:
                flash(f"Unexpected error during PDF extraction: {str(e)}", "error")
                return render_template(
                    "index.html",
                    uploaded_file=base_safe_name,
                    recent_reports=recent_reports,
                )
            finally:
                # Security & Privacy: Clean up uploaded PDF from disk immediately after extraction
                if os.path.exists(save_path):
                    try:
                        os.remove(save_path)
                    except OSError:
                        pass

            # Step 2: Extract structured JSON using Gemini
            medical_data = None
            json_formatted = None
            gemini_error = None
            saved_report_id = None

            try:
                # Never saves report unless Gemini output passes Pydantic validation inside gemini_service
                medical_data = extract_medical_data_with_gemini(extracted_text)
                json_formatted = json.dumps(medical_data, indent=2)

                # Step 3: Persist validated data into SQLite
                try:
                    saved_report_id = save_medical_report(medical_data)
                    flash(
                        f"Report successfully validated and saved to database (Report ID: #{saved_report_id})!",
                        "success",
                    )
                    # Refresh recent reports list after insertion
                    recent_reports = get_recent_reports()
                except DatabaseError as dbe:
                    flash(f"Extracted data successfully, but database save failed: {str(dbe)}", "error")

            except GeminiServiceError as ge:
                gemini_error = str(ge)
                flash(f"Gemini processing error: {gemini_error}", "warning")
            except Exception as e:
                gemini_error = str(e)
                flash(f"Unexpected error from Gemini service: {gemini_error}", "warning")

            return render_template(
                "index.html",
                uploaded_file=base_safe_name,
                extracted_text=extracted_text,
                medical_data=medical_data,
                json_formatted=json_formatted,
                gemini_error=gemini_error,
                saved_report_id=saved_report_id,
                recent_reports=recent_reports,
            )
        else:
            flash("Invalid file format. Please upload a valid .pdf file.", "error")
            return redirect(request.url)

    return render_template("index.html", recent_reports=recent_reports)


@app.route("/report/<int:report_id>", methods=["GET"])
def view_report(report_id: int):
    """
    Displays a previously stored medical report from the SQLite database.
    """
    try:
        report = get_report_by_id(report_id)
        if not report:
            flash(f"Medical report #{report_id} was not found in the database.", "error")
            return redirect(url_for("upload_pdf"))

        recent_reports = get_recent_reports()
        medical_data = report["data"]
        json_formatted = json.dumps(medical_data, indent=2)

        return render_template(
            "index.html",
            medical_data=medical_data,
            json_formatted=json_formatted,
            viewing_report_id=report["id"],
            viewing_report_date=report["created_at"],
            recent_reports=recent_reports,
        )
    except DatabaseError as e:
        flash(f"Error accessing database: {str(e)}", "error")
        return redirect(url_for("upload_pdf"))


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host="127.0.0.1", port=port)
