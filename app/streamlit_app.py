from __future__ import annotations

import tempfile
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import streamlit as st

from invoice_data_extractor import (
    DEFAULT_DB_PATH,
    SUPPORTED_IMAGE_EXTENSIONS,
    InvoiceData,
    apply_validation,
    configure_tesseract,
    export_invoices,
    extract_invoice_data,
    file_sha256,
    import_runtime_dependencies,
    load_recent_history,
    lookup_duplicate_reason,
    ocr_document,
    save_invoice_history,
)


st.set_page_config(page_title="Invoice Data Extractor", layout="wide")


def rows_to_dataframe(rows: list[InvoiceData]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                **asdict(row),
                "validation_issues": "; ".join(row.validation_issues),
                "line_items": len(row.line_items),
            }
            for row in rows
        ]
    )


def line_items_dataframe(rows: list[InvoiceData]) -> pd.DataFrame:
    records = []
    for invoice in rows:
        for index, item in enumerate(invoice.line_items, start=1):
            records.append(
                {
                    "filename": invoice.filename,
                    "invoice_number": invoice.invoice_number,
                    "line": index,
                    "description": item.description,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "tax": item.tax,
                    "total": item.total,
                    "raw_text": item.raw_text,
                }
            )
    return pd.DataFrame(records)


def dataframe_to_rows(dataframe: pd.DataFrame) -> list[InvoiceData]:
    def to_bool(value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y"}
        return bool(value)

    rows: list[InvoiceData] = []
    for record in dataframe.fillna("").to_dict(orient="records"):
        row = InvoiceData(
            filename=str(record.get("filename", "")),
            invoice_number=str(record.get("invoice_number", "")),
            date=str(record.get("date", "")),
            subtotal=str(record.get("subtotal", "")),
            tax=str(record.get("tax", "")),
            total=str(record.get("total", "")),
            account_number=str(record.get("account_number", "")),
            account_name=str(record.get("account_name", "")),
            source_path=str(record.get("source_path", "")),
            source_hash=str(record.get("source_hash", "")),
            duplicate=to_bool(record.get("duplicate", False)),
            duplicate_reason=str(record.get("duplicate_reason", "")),
            validation_status=str(record.get("validation_status", "unknown")),
            validation_issues=[
                issue.strip()
                for issue in str(record.get("validation_issues", "")).split(";")
                if issue.strip()
            ],
        )
        rows.append(row)
    return rows


def merge_line_items(
    edited_rows: list[InvoiceData], original_rows: list[InvoiceData]
) -> list[InvoiceData]:
    by_filename = {row.filename: row for row in original_rows}
    merged_rows: list[InvoiceData] = []

    for row in edited_rows:
        original = by_filename.get(row.filename)
        if original:
            row.line_items = original.line_items
        merged_rows.append(row)

    return merged_rows


def render_sidebar() -> tuple[str, bool, str, str]:
    with st.sidebar:
        st.header("Settings")
        tesseract_cmd = st.text_input(
            "Tesseract executable",
            value="",
            placeholder=r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        )
        export_format = st.selectbox("Export format", ["xlsx", "csv", "json"], index=0)
        db_path = st.text_input("History database", value=str(DEFAULT_DB_PATH))
        show_history = st.checkbox("Show recent history", value=True)
        st.caption("Leave the executable blank when Tesseract is already on PATH.")
    return tesseract_cmd.strip(), show_history, export_format, db_path.strip()


def build_download_payload(files: list[Path]) -> tuple[bytes, str]:
    if len(files) == 1:
        path = files[0]
        return path.read_bytes(), path.name

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, arcname=path.name)
    return buffer.getvalue(), "invoice_exports.zip"


def main() -> None:
    st.title("Invoice Data Extractor")
    st.caption("Upload invoice images, extract fields, validate totals, and download the result.")

    tesseract_cmd, show_history, export_format, db_path_value = render_sidebar()
    allowed_extensions = sorted(ext.lstrip(".") for ext in SUPPORTED_IMAGE_EXTENSIONS)
    uploaded_files = st.file_uploader(
        "Upload invoice images",
        type=allowed_extensions,
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.info("Upload one or more invoice images to start.")
        return

    preview_columns = st.columns(min(len(uploaded_files), 4))
    for index, uploaded_file in enumerate(uploaded_files[:4]):
        with preview_columns[index % len(preview_columns)]:
            st.image(uploaded_file, caption=uploaded_file.name, use_container_width=True)

    if len(uploaded_files) > 4:
        st.caption(f"{len(uploaded_files) - 4} more file(s) selected.")

    if not st.button("Extract Data", type="primary"):
        return

    try:
        cv2_module, pytesseract_module, _, _, _ = import_runtime_dependencies()
        configure_tesseract(pytesseract_module, tesseract_cmd or None)
    except RuntimeError as exc:
        st.error(str(exc))
        return

    db_path = Path(db_path_value).expanduser().resolve()
    extracted_rows: list[InvoiceData] = []
    failures: list[tuple[str, str]] = []
    seen_hashes: set[str] = set()
    seen_invoice_numbers: set[str] = set()

    progress = st.progress(0)
    status = st.empty()

    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        for index, uploaded_file in enumerate(uploaded_files, start=1):
            status.write(f"Processing {uploaded_file.name}")
            image_path = temp_dir / Path(uploaded_file.name).name
            image_path.write_bytes(uploaded_file.getbuffer())

            try:
                document = ocr_document(image_path, cv2_module, pytesseract_module, "eng")
                invoice = extract_invoice_data(uploaded_file.name, document.text, document.lines)
                invoice.source_path = uploaded_file.name
                invoice.source_hash = file_sha256(image_path)
                apply_validation(invoice)

                duplicate_reasons: list[str] = []
                if invoice.source_hash in seen_hashes:
                    duplicate_reasons.append("same_uploaded_file")
                if invoice.invoice_number and invoice.invoice_number in seen_invoice_numbers:
                    duplicate_reasons.append("repeated_invoice_number")
                db_duplicate = lookup_duplicate_reason(db_path, invoice.source_hash, invoice.invoice_number)
                if db_duplicate:
                    duplicate_reasons.append(db_duplicate)

                invoice.duplicate = bool(duplicate_reasons)
                invoice.duplicate_reason = ", ".join(sorted(set(duplicate_reasons)))

                save_invoice_history(db_path, invoice, source_path=uploaded_file.name)
                extracted_rows.append(invoice)
                seen_hashes.add(invoice.source_hash)
                if invoice.invoice_number:
                    seen_invoice_numbers.add(invoice.invoice_number)
            except Exception as exc:
                failures.append((uploaded_file.name, str(exc)))
                extracted_rows.append(InvoiceData(filename=uploaded_file.name, validation_status="failed"))

            progress.progress(index / len(uploaded_files))

    status.empty()

    if failures:
        st.warning("Some files could not be processed.")
        for filename, error in failures:
            st.caption(f"{filename}: {error}")

    summary_dataframe = rows_to_dataframe(extracted_rows)
    edited_summary = st.data_editor(summary_dataframe, hide_index=True, use_container_width=True)

    st.subheader("Line Items")
    st.dataframe(line_items_dataframe(extracted_rows), use_container_width=True)

    st.subheader("Validation")
    validation_rows = summary_dataframe[["filename", "validation_status", "validation_issues", "duplicate_reason"]]
    st.dataframe(validation_rows, use_container_width=True)

    export_rows = merge_line_items(dataframe_to_rows(edited_summary), extracted_rows)
    with tempfile.TemporaryDirectory() as export_dir_name:
        export_dir = Path(export_dir_name)
        output_files = export_invoices(export_rows, export_dir / "invoice_export", export_format)
        payload, download_name = build_download_payload(output_files)
        st.download_button(
            "Download Export",
            data=payload,
            file_name=download_name,
        )

    if show_history:
        st.subheader("Recent History")
        history = load_recent_history(db_path, limit=20)
        if history:
            st.dataframe(pd.DataFrame(history), use_container_width=True)
        else:
            st.caption("No saved history yet.")


if __name__ == "__main__":
    main()
