"""
pdf_extractor.py - PDF Text Extraction Module for DocuMed AI

This module extracts raw text content from uploaded medical PDF documents
using pypdf, with robust error handling for invalid, corrupted, empty,
or password-protected files.
"""

import os
from pypdf import PdfReader
from pypdf.errors import PdfReadError, FileNotDecryptedError, EmptyFileError


class PDFExtractionError(Exception):
    """Custom exception raised when PDF text extraction fails."""
    pass


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extracts text from all pages of an uploaded PDF file.

    Args:
        file_path (str): Path to the PDF file on disk.

    Returns:
        str: Cleaned text extracted from all pages of the PDF.

    Raises:
        PDFExtractionError: If the file is missing, empty, corrupted,
                            password-protected, or contains no extractable text.
    """
    # 1. Check if the file exists
    if not os.path.exists(file_path):
        raise PDFExtractionError(f"PDF file not found: {file_path}")

    # 2. Check for empty file (0 bytes)
    try:
        if os.path.getsize(file_path) == 0:
            raise PDFExtractionError("The uploaded file is empty (0 bytes).")
    except OSError as e:
        raise PDFExtractionError(f"Could not access file: {str(e)}")

    # 3. Open and parse the PDF with pypdf
    try:
        reader = PdfReader(file_path)
    except EmptyFileError:
        raise PDFExtractionError("The uploaded file is empty.")
    except PdfReadError as e:
        raise PDFExtractionError(f"Invalid or corrupted PDF file: {str(e)}")
    except Exception as e:
        raise PDFExtractionError(f"Failed to read PDF document: {str(e)}")

    # 4. Handle password-protected / encrypted PDFs
    if reader.is_encrypted:
        is_decrypted = False
        try:
            # Some PDFs have an empty password allowing read access
            decrypt_result = reader.decrypt("")
            if decrypt_result != 0:
                is_decrypted = True
        except Exception:
            is_decrypted = False

        if not is_decrypted:
            raise PDFExtractionError(
                "This PDF is password-protected and cannot be read without a password."
            )

    # 5. Check if the PDF has any pages
    if len(reader.pages) == 0:
        raise PDFExtractionError("The PDF document contains no pages.")

    # 6. Extract text from all pages
    extracted_pages = []
    for page_index, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
            cleaned_text = page_text.strip()
            if cleaned_text:
                extracted_pages.append(cleaned_text)
        except FileNotDecryptedError:
            raise PDFExtractionError(
                "This PDF is password-protected and cannot be read."
            )
        except Exception as e:
            # Continue extracting remaining pages if a single page encounters an issue
            continue

    # 7. Check if any extractable text was found
    if not extracted_pages:
        raise PDFExtractionError(
            "No extractable text found in this PDF. It may be a scanned image or empty document."
        )

    # Combine all extracted pages with readable paragraph separation
    return "\n\n".join(extracted_pages)
