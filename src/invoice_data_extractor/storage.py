from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path

from invoice_data_extractor.extractor import InvoiceData


DEFAULT_DB_PATH = Path(".invoice_history.sqlite3")


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(_connect(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                source_path TEXT,
                source_hash TEXT NOT NULL,
                invoice_number TEXT,
                date TEXT,
                subtotal TEXT,
                tax TEXT,
                total TEXT,
                account_number TEXT,
                account_name TEXT,
                validation_status TEXT,
                validation_issues_json TEXT,
                duplicate INTEGER NOT NULL DEFAULT 0,
                duplicate_reason TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS line_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                line_index INTEGER NOT NULL,
                description TEXT,
                quantity TEXT,
                unit_price TEXT,
                tax TEXT,
                total TEXT,
                raw_text TEXT,
                FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_invoices_hash ON invoices(source_hash)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number)"
        )
        conn.commit()


def lookup_duplicate_reason(db_path: Path, source_hash: str, invoice_number: str) -> str:
    if not db_path.exists():
        return ""

    with closing(_connect(db_path)) as conn:
        if source_hash:
            row = conn.execute(
                "SELECT 1 FROM invoices WHERE source_hash = ? LIMIT 1", (source_hash,)
            ).fetchone()
            if row:
                return "same_uploaded_file"

        if invoice_number:
            row = conn.execute(
                "SELECT 1 FROM invoices WHERE invoice_number = ? LIMIT 1", (invoice_number,)
            ).fetchone()
            if row:
                return "repeated_invoice_number"

    return ""


def save_invoice_history(db_path: Path, invoice: InvoiceData, source_path: str = "") -> int:
    init_database(db_path)
    created_at = datetime.now(timezone.utc).isoformat()

    with closing(_connect(db_path)) as conn:
        cursor = conn.execute(
            """
            INSERT INTO invoices (
                filename, source_path, source_hash, invoice_number, date, subtotal, tax, total,
                account_number, account_name, validation_status, validation_issues_json,
                duplicate, duplicate_reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invoice.filename,
                source_path,
                invoice.source_hash,
                invoice.invoice_number,
                invoice.date,
                invoice.subtotal,
                invoice.tax,
                invoice.total,
                invoice.account_number,
                invoice.account_name,
                invoice.validation_status,
                json.dumps(invoice.validation_issues),
                int(invoice.duplicate),
                invoice.duplicate_reason,
                created_at,
            ),
        )
        invoice_id = int(cursor.lastrowid)

        for index, item in enumerate(invoice.line_items, start=1):
            conn.execute(
                """
                INSERT INTO line_items (
                    invoice_id, line_index, description, quantity, unit_price, tax, total, raw_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_id,
                    index,
                    item.description,
                    item.quantity,
                    item.unit_price,
                    item.tax,
                    item.total,
                    item.raw_text,
                ),
            )

        conn.commit()

    return invoice_id


def load_recent_history(db_path: Path, limit: int = 20) -> list[dict[str, object]]:
    if not db_path.exists():
        return []

    with closing(_connect(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT id, filename, invoice_number, date, total, duplicate, duplicate_reason,
                   validation_status, created_at
            FROM invoices
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        {
            "id": row[0],
            "filename": row[1],
            "invoice_number": row[2],
            "date": row[3],
            "total": row[4],
            "duplicate": bool(row[5]),
            "duplicate_reason": row[6] or "",
            "validation_status": row[7],
            "created_at": row[8],
        }
        for row in rows
    ]
