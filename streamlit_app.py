from __future__ import annotations

import tempfile
from dataclasses import asdict
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from main import (
    SUPPORTED_IMAGE_EXTENSIONS,
    InvoiceData,
    configure_tesseract,
    extract_invoice_data,
    import_runtime_dependencies,
    ocr_image,
    write_workbook,
)


st.set_page_config(
    page_title="Invoice Data Extractor",
    layout="wide",
)


def make_excel_download(rows: list[InvoiceData]) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_file:
        temp_path = Path(temp_file.name)

    try:
        _, _, Workbook, Alignment, Font = import_runtime_dependencies()
        write_workbook(rows, temp_path, (Workbook, Alignment, Font))
        return temp_path.read_bytes()
    finally:
        temp_path.unlink(missing_ok=True)


def write_upload_to_temp(uploaded_file, temp_dir: Path) -> Path:
    safe_name = Path(uploaded_file.name).name
    target_path = temp_dir / safe_name
    target_path.write_bytes(uploaded_file.getbuffer())
    return target_path


def rows_to_dataframe(rows: list[InvoiceData]) -> pd.DataFrame:
    return pd.DataFrame([asdict(row) for row in rows]).rename(
        columns={
            "filename": "Filename",
            "invoice_number": "Invoice Number",
            "date": "Date",
            "subtotal": "Subtotal",
            "tax": "Tax",
            "total": "Total",
            "account_number": "Account Number",
            "account_name": "Account Name",
        }
    )


def dataframe_to_rows(dataframe: pd.DataFrame) -> list[InvoiceData]:
    rows: list[InvoiceData] = []
    for record in dataframe.fillna("").to_dict(orient="records"):
        rows.append(
            InvoiceData(
                filename=str(record.get("Filename", "")),
                invoice_number=str(record.get("Invoice Number", "")),
                date=str(record.get("Date", "")),
                subtotal=str(record.get("Subtotal", "")),
                tax=str(record.get("Tax", "")),
                total=str(record.get("Total", "")),
                account_number=str(record.get("Account Number", "")),
                account_name=str(record.get("Account Name", "")),
            )
        )
    return rows


def render_sidebar() -> tuple[str, bool]:
    with st.sidebar:
        st.header("Settings")
        tesseract_cmd = st.text_input(
            "Tesseract executable",
            value="",
            placeholder=r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        )
        show_ocr_text = st.checkbox("Show OCR text", value=False)
        st.caption("Leave the executable blank when Tesseract is already on PATH.")
    return tesseract_cmd.strip(), show_ocr_text


def main() -> None:
    st.title("Invoice Data Extractor")
    st.caption("Upload invoice images, extract key fields, and download the result as Excel.")

    tesseract_cmd, show_ocr_text = render_sidebar()

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
    except SystemExit as exc:
        st.error(str(exc))
        return

    extracted_rows: list[InvoiceData] = []
    ocr_text_by_file: dict[str, str] = {}
    failures: list[tuple[str, str]] = []

    progress = st.progress(0)
    status = st.empty()

    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        for index, uploaded_file in enumerate(uploaded_files, start=1):
            status.write(f"Processing {uploaded_file.name}")
            image_path = write_upload_to_temp(uploaded_file, temp_dir)

            try:
                text = ocr_image(image_path, cv2_module, pytesseract_module, "eng")
                ocr_text_by_file[uploaded_file.name] = text
                extracted_rows.append(extract_invoice_data(uploaded_file.name, text))
            except Exception as exc:
                failures.append((uploaded_file.name, str(exc)))
                extracted_rows.append(InvoiceData(filename=uploaded_file.name))

            progress.progress(index / len(uploaded_files))

    status.empty()

    if failures:
        st.warning("Some files could not be processed.")
        for filename, error in failures:
            st.caption(f"{filename}: {error}")

    dataframe = rows_to_dataframe(extracted_rows)
    st.subheader("Extracted Data")
    edited_dataframe = st.data_editor(dataframe, hide_index=True, use_container_width=True)

    excel_bytes = make_excel_download(dataframe_to_rows(edited_dataframe))
    st.download_button(
        "Download Excel",
        data=excel_bytes,
        file_name="extracted_invoice_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    if show_ocr_text and ocr_text_by_file:
        st.subheader("OCR Text")
        for filename, text in ocr_text_by_file.items():
            with st.expander(filename):
                st.text_area(filename, text, height=220, label_visibility="collapsed")


if __name__ == "__main__":
    main()
