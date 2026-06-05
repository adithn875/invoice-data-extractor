from __future__ import annotations

import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


@dataclass
class InvoiceData:
    filename: str
    invoice_number: str = ""
    date: str = ""
    subtotal: str = ""
    tax: str = ""
    total: str = ""
    account_number: str = ""
    account_name: str = ""


FIELD_PATTERNS = {
    "invoice_number": [
        r"\bInvoice[^\S\r\n]*(?:Number|No\.?|#)?[^\S\r\n]*[:#;\-][^\S\r\n]*#?[^\S\r\n]*([A-Z0-9][A-Z0-9\-\/]+)",
        r"\bInv(?:oice)?[^\S\r\n]*[:#;\-][^\S\r\n]*#?[^\S\r\n]*([A-Z0-9][A-Z0-9\-\/]+)",
    ],
    "date": [
        r"\b(?:Invoice\s*)?Date\s*[:#-]?\s*([0-3]?\d[./-][01]?\d[./-](?:\d{4}|\d{2}))",
        r"\b([0-3]?\d[./-][01]?\d[./-](?:\d{4}|\d{2}))\b",
        r"\b([A-Z][a-z]{2,8}[.\s]+\d{1,2}[,\s.]+\d{4})\b",
        r"\b([A-Z][a-z]{2,8}\s+\d{1,2},?\s+\d{4})\b",
    ],
    "subtotal": [
        r"\bSub\s*[- ]?\s*Total\s*[:#-]?\s*(?:Rs\.?|INR|\$)?\s*([0-9,]+(?:\.\d{1,2})?)",
        r"\bAmount\s*Before\s*Tax\s*[:#-]?\s*(?:Rs\.?|INR|\$)?\s*([0-9,]+(?:\.\d{1,2})?)",
    ],
    "tax": [
        r"\b(?:Tax|GST|CGST|SGST|VAT)\s*[:#-]?\s*(?:Rs\.?|INR|\$)?\s*([0-9,]+(?:\.\d{1,2})?%?)",
    ],
    "total": [
        r"\bAmount\s*Due\s*[:#-]?\s*(?:Rs\.?|INR|\$|%)?\s*([0-9,]+(?:\.\d{1,2})?)",
        r"\bGrand\s*Total\s*[:#-]?\s*(?:Rs\.?|INR|\$)?\s*([0-9,]+(?:\.\d{1,2})?)",
        r"\bTotal\s*(?:Amount|Due)?\s*[:#-]?\s*(?:Rs\.?|INR|\$)?\s*([0-9,]+(?:\.\d{1,2})?)",
    ],
    "account_number": [
        r"\bAccount\s*(?:Number|No\.?)\s*[:#.-]?\s*([0-9][0-9 \-]{3,})",
        r"\bA\/c\s*No\.?\s*[:#.-]?\s*([0-9][0-9 \-]{3,})",
    ],
    "account_name": [
        r"\bAccount\s*Name\s*[:#-]?\s*([^\n\r]+)",
        r"\bA\/c\s*Name\s*[:#-]?\s*([^\n\r]+)",
        r"\bBill\s*To\s*[:#-]?\s*([^\n\r]+)",
    ],
}


def import_runtime_dependencies():
    try:
        import cv2
        import pytesseract
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font
    except ImportError as exc:
        missing = exc.name or "a required package"
        raise RuntimeError(
            f"Missing dependency: {missing}. Install project dependencies with: "
            "python -m pip install -r requirements.txt"
        ) from exc

    return cv2, pytesseract, Workbook, Alignment, Font


def configure_tesseract(pytesseract_module, tesseract_cmd: str | None) -> None:
    if tesseract_cmd:
        if not Path(tesseract_cmd).exists():
            raise RuntimeError(f"Tesseract executable was not found: {tesseract_cmd}")
        pytesseract_module.pytesseract.tesseract_cmd = tesseract_cmd
        return

    if shutil.which("tesseract"):
        return

    default_windows_paths = [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ]
    for path in default_windows_paths:
        if path.exists():
            pytesseract_module.pytesseract.tesseract_cmd = str(path)
            return

    raise RuntimeError(
        "Tesseract OCR is not installed or not on PATH. Install it, then rerun with "
        "--tesseract-cmd C:\\Path\\To\\tesseract.exe or set TESSERACT_CMD."
    )


def discover_images(input_path: Path, recursive: bool) -> list[Path]:
    if input_path.is_file():
        if input_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            raise ValueError(f"Unsupported image type: {input_path}")
        return [input_path]

    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    pattern = "**/*" if recursive else "*"
    images = [
        path
        for path in input_path.glob(pattern)
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
    ]
    return sorted(images)


def preprocess_image(image_path: Path, cv2_module):
    image = cv2_module.imread(str(image_path), cv2_module.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError("OpenCV could not read the image")

    image = cv2_module.resize(image, None, fx=2, fy=2, interpolation=cv2_module.INTER_CUBIC)
    image = cv2_module.fastNlMeansDenoising(image, None, 12, 7, 21)
    image = cv2_module.adaptiveThreshold(
        image,
        255,
        cv2_module.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2_module.THRESH_BINARY,
        31,
        10,
    )
    return image


def normalize_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_value(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" :-#\t")
    return value.strip()


def extract_field(text: str, patterns: Iterable[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return clean_value(match.group(1))
    return ""


def extract_invoice_data(filename: str, text: str) -> InvoiceData:
    text = normalize_text(text)
    values = {
        field_name: extract_field(text, patterns)
        for field_name, patterns in FIELD_PATTERNS.items()
    }
    return InvoiceData(filename=filename, **values)


def ocr_image(image_path: Path, cv2_module, pytesseract_module, lang: str) -> str:
    processed = preprocess_image(image_path, cv2_module)
    return pytesseract_module.image_to_string(processed, lang=lang, config="--psm 6")


def write_workbook(rows: list[InvoiceData], output_path: Path, workbook_classes) -> None:
    Workbook, Alignment, Font = workbook_classes

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Invoices"

    headers = [
        "Filename",
        "Invoice Number",
        "Date",
        "Subtotal",
        "Tax",
        "Total",
        "Account Number",
        "Account Name",
    ]
    worksheet.append(headers)

    for row in rows:
        values = asdict(row)
        worksheet.append(
            [
                values["filename"],
                values["invoice_number"],
                values["date"],
                values["subtotal"],
                values["tax"],
                values["total"],
                values["account_number"],
                values["account_name"],
            ]
        )

    for cell in worksheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    for column in worksheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column)
        worksheet.column_dimensions[column[0].column_letter].width = min(max_length + 4, 45)

    workbook.save(output_path)
