# Invoice Data Extractor

Extract invoice fields from image files with OCR and export the results to an Excel workbook.

## Features

- Processes PNG, JPG, JPEG, TIFF, and BMP invoice images.
- Extracts invoice number, date, subtotal, tax, total, account number, and account name.
- Writes results to a formatted `.xlsx` file.
- Supports a single image, a folder of images, or recursive folder scanning.
- Allows custom Tesseract executable paths through an argument or environment variable.

## Requirements

- Python 3.10+
- Tesseract OCR installed on your system

Install Python packages:

```bash
python -m pip install -r requirements.txt
```

Install Tesseract:

- Windows: install from the official UB Mannheim Windows builds, then note the `tesseract.exe` path.
- macOS: `brew install tesseract`
- Linux: `sudo apt install tesseract-ocr`

## Usage

Run against the sample images in the project root:

```bash
python main.py
```

Run against a folder:

```bash
python main.py --input path/to/invoices --output extracted_invoice_data.xlsx
```

Run recursively:

```bash
python main.py --input path/to/invoices --recursive
```

On Windows, if Tesseract is not on `PATH`, pass the executable path:

```bash
python main.py --tesseract-cmd "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

You can also set:

```bash
set TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

## Troubleshooting

Use `--debug-text` to save OCR text files beside the Excel output. This helps tune regex patterns when an invoice layout is not detected correctly.

```bash
python main.py --debug-text
```

## Streamlit App

Install dependencies, then launch the browser UI:

```bash
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

Use the sidebar to enter a Tesseract executable path if it is not already on `PATH`.
