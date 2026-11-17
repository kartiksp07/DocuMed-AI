"""
database.py - SQLite Storage Layer for DocuMed AI

This module handles initializing the SQLite database, storing validated
medical report JSON objects, and querying stored reports from the instance/ directory.
"""

from contextlib import contextmanager
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional

# Path to the SQLite database file inside the instance directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DATABASE_PATH = os.path.join(INSTANCE_DIR, "documed.db")


class DatabaseError(Exception):
    """Custom exception raised when database operations fail."""
    pass


@contextmanager
def get_db_connection():
    """
    Context manager that yields an open SQLite connection with Row factory,
    commits transactions automatically, and guarantees connection closure.
    """
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise DatabaseError(f"Database error: {str(e)}")
    finally:
        if conn:
            conn.close()


def init_db():
    """
    Initializes the database schema and creates the medical_reports table if it doesn't exist.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS medical_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_name TEXT,
                    report_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
    except DatabaseError:
        raise
    except Exception as e:
        raise DatabaseError(f"Failed to initialize database: {str(e)}")


def save_medical_report(report_data: Dict[str, Any]) -> int:
    """
    Saves a successfully validated medical report dictionary into SQLite.

    Args:
        report_data (dict): Validated medical report data.

    Returns:
        int: The newly inserted report record ID.

    Raises:
        DatabaseError: If data is invalid or SQL insertion fails.
    """
    if not isinstance(report_data, dict) or not report_data:
        raise DatabaseError("Cannot save invalid or empty report data to database.")

    try:
        # Serialize report dictionary to valid JSON
        json_content = json.dumps(report_data, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        raise DatabaseError(f"Failed to serialize medical report to JSON: {str(e)}")

    patient_name = report_data.get("patient_name") or "Unspecified Patient"

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Parameterized query to prevent SQL injection
            cursor.execute(
                """
                INSERT INTO medical_reports (patient_name, report_json)
                VALUES (?, ?)
                """,
                (patient_name, json_content),
            )
            return cursor.lastrowid
    except DatabaseError:
        raise
    except Exception as e:
        raise DatabaseError(f"Database error while saving report: {str(e)}")


def get_recent_reports(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retrieves the most recent saved medical reports.

    Args:
        limit (int): Maximum number of reports to retrieve.

    Returns:
        list: List of dictionaries with report metadata.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, patient_name, created_at
                FROM medical_reports
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "patient_name": row["patient_name"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
    except DatabaseError:
        raise
    except Exception as e:
        raise DatabaseError(f"Failed to fetch recent reports: {str(e)}")


def get_report_by_id(report_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves a single medical report by its ID, parsing the stored JSON.

    Args:
        report_id (int): Primary key ID of the report.

    Returns:
        dict or None: Report record with parsed medical data, or None if not found.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, patient_name, report_json, created_at
                FROM medical_reports
                WHERE id = ?
                """,
                (report_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            try:
                parsed_data = json.loads(row["report_json"])
            except json.JSONDecodeError as e:
                raise DatabaseError(f"Corrupted JSON in report #{report_id}: {str(e)}")

            return {
                "id": row["id"],
                "patient_name": row["patient_name"],
                "created_at": row["created_at"],
                "data": parsed_data,
            }
    except DatabaseError:
        raise
    except Exception as e:
        raise DatabaseError(f"Failed to retrieve report #{report_id}: {str(e)}")


# Automatically ensure table exists when module is imported
init_db()
