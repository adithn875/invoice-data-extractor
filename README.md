# Invoice Data Extractor

Extract invoice fields from images with OCR and export the results to Excel.

## Project Structure

```text
invoice-data-extractor/
├── app/                         # Streamlit frontend
│   └── streamlit_app.py
├── examples/
│   └── invoices/                # Sample invoice images
├── src/
│   └── invoice_data_extractor/  # Reusable Python package
│       ├── __init__.py
│       ├── cli.py
│       └── extractor.py
├── tests/                       # Unit tests
├── pyproject.toml               # Package metadata and CLI entry point
├── requirements.txt             # Runtime dependencies
└── README.md
```

## Features

- Processes PNG, JPG, JPEG, TIFF, and BMP invoice images.
- Extracts invoice number, date, subtotal, tax, total, account number, and account name.
- Exports results to a formatted `.xlsx` workbook.
- Provides both a command-line interface and a Streamlit browser UI.
- Supports custom Tesseract executable paths.

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

Install Tesseract:

- Windows: install Tesseract OCR and note the `tesseract.exe` path.
- macOS: `brew install tesseract`
- Linux: `sudo apt install tesseract-ocr`

## Command Line Usage

After editable install:

```bash
invoice-extract
```

The default input folder is `examples/invoices`.

Run against a custom folder:

```bash
invoice-extract --input path/to/invoices --output extracted_invoice_data.xlsx
```

Run recursively:

```bash
invoice-extract --input path/to/invoices --recursive
```

On Windows, if Tesseract is not on `PATH`, pass the executable path:

```bash
invoice-extract --tesseract-cmd "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

You can also set:

```bash
set TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

## Streamlit App

Launch the browser UI:

```bash
python -m streamlit run app/streamlit_app.py
```

Use the sidebar to enter the Tesseract executable path if it is not already on `PATH`.

## Tests

```bash
python -m unittest discover -s tests
```
