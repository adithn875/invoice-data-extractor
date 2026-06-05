# Invoice Data Extractor

Extract invoice fields from images with OCR, validate totals, store processing history, and export the results to Excel, CSV, or JSON.

## Project Structure

```text
invoice-data-extractor/
|-- app/
|   `-- streamlit_app.py
|-- examples/
|   `-- invoices/
|-- src/
|   `-- invoice_data_extractor/
|       |-- __init__.py
|       |-- cli.py
|       |-- export.py
|       |-- extractor.py
|       |-- storage.py
|       `-- validation.py
|-- tests/
|-- pyproject.toml
|-- requirements.txt
`-- README.md
```

## Features

- OCR via Tesseract with layout-aware line reconstruction.
- Keyword-proximity extraction for invoice metadata.
- Line-item extraction for description, quantity, unit price, tax, and total.
- Validation rules for subtotal, tax, total, and line-item totals.
- Duplicate detection by invoice number and uploaded file hash.
- SQLite history storage for processed invoices.
- Export to Excel, CSV, or JSON.
- Streamlit frontend for upload, preview, validation, and download.

## Requirements

- Python 3.10+
- Tesseract OCR installed on your system

Install Python dependencies:

```bash
python -m pip install -r requirements.txt
```

For local development, install the package in editable mode:

```bash
python -m pip install -e .
```

## Command Line Usage

Run the extractor against the sample invoices:

```bash
invoice-extract
```

The default input folder is `examples/invoices`.

Export as CSV or JSON:

```bash
invoice-extract --format csv
invoice-extract --format json
```

Run against your own folder:

```bash
invoice-extract --input path/to/invoices --recursive
```

Set a custom Tesseract executable if needed:

```bash
invoice-extract --tesseract-cmd "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

The invoice history database is stored in `.invoice_history.sqlite3` by default.

## Streamlit App

Launch the browser UI:

```bash
python -m streamlit run app/streamlit_app.py
```

The app lets you:

- Upload multiple invoice images.
- View extracted summary fields and line items.
- Check validation and duplicate status.
- Choose an export format.
- Download the exported file set.
- Review recent processing history from SQLite.

## Tests

```bash
python -m unittest discover -s tests
```
