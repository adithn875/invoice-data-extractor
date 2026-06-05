from __future__ import annotations

import hashlib
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence


SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


@dataclass
class InvoiceLineItem:
    description: str
    quantity: str = ""
    unit_price: str = ""
    tax: str = ""
    total: str = ""
    raw_text: str = ""


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
    source_path: str = ""
    source_hash: str = ""
    duplicate: bool = False
    duplicate_reason: str = ""
    validation_status: str = "unknown"
    validation_issues: list[str] = field(default_factory=list)
    line_items: list[InvoiceLineItem] = field(default_factory=list)


@dataclass
class OcrDocument:
    text: str
    lines: list[str]


FIELD_SPECS = {
    "invoice_number": {
        "labels": ["invoice number", "invoice no", "invoice #", "invoice"],
        "patterns": [
            r"\bInvoice[^\S\r\n]*(?:Number|No\.?|#)?[^\S\r\n]*[:#;\-]?[^\S\r\n]*#?[^\S\r\n]*([A-Z0-9][A-Z0-9\-\/]+)\b",
            r"\bInv(?:oice)?[^\S\r\n]*[:#;\-]?[^\S\r\n]*#?[^\S\r\n]*([A-Z0-9][A-Z0-9\-\/]+)\b",
        ],
    },
    "date": {
        "labels": ["invoice date", "date"],
        "patterns": [
            r"\b(?:Invoice\s*)?Date\s*[:#-]?\s*([0-3]?\d[./-][01]?\d[./-](?:\d{4}|\d{2}))\b",
            r"\b([0-3]?\d[./-][01]?\d[./-](?:\d{4}|\d{2}))\b",
            r"\b([A-Z]{3,9}[.\s]+\d{1,2}[,\s.]+\d{4})\b",
            r"\b([A-Z][a-z]{2,8}[.\s]+\d{1,2}[,\s.]+\d{4})\b",
            r"\b([A-Z][a-z]{2,8}\s+\d{1,2},?\s+\d{4})\b",
        ],
    },
    "subtotal": {
        "labels": ["subtotal", "sub total", "amount before tax"],
        "patterns": [
            r"\bSub\s*[- ]?\s*Total\s*[:#-]?\s*(?:Rs\.?|INR|\$|₹)?\s*([~%$₹]?[0-9,]+(?:\.\d{1,2})?)\b",
            r"\bAmount\s*Before\s*Tax\s*[:#-]?\s*(?:Rs\.?|INR|\$|₹)?\s*([~%$₹]?[0-9,]+(?:\.\d{1,2})?)\b",
        ],
    },
    "tax": {
        "labels": ["tax", "gst", "cgst", "sgst", "vat"],
        "patterns": [
            r"\b(?:Tax|GST|CGST|SGST|VAT)\s*[:#-]?\s*(?:Rs\.?|INR|\$|₹)?\s*([0-9,]+(?:\.\d{1,2})?%?)",
        ],
    },
    "total": {
        "labels": ["grand total", "amount due", "total amount", "total due", "balance due", "total"],
        "patterns": [
            r"\b(?:Grand\s*Total|Amount\s*Due|Total\s*Amount|Total\s*Due|Balance\s*Due|Total)\s*[:#;\-]?\s*(?:Rs\.?|INR|\$|₹)?\s*([~%$₹]?[0-9,]+(?:\.\d{1,2})?)\b",
        ],
    },
    "account_number": {
        "labels": ["account number", "account no", "a/c no", "bank account no"],
        "patterns": [
            r"\bAccount\s*(?:Number|No\.?)\s*[:#.-]?\s*([A-Z0-9][A-Z0-9 \-]{3,})\b",
            r"\bA\/c\s*No\.?\s*[:#.-]?\s*([A-Z0-9][A-Z0-9 \-]{3,})\b",
        ],
    },
    "account_name": {
        "labels": ["account name", "a/c name", "beneficiary name", "payee"],
        "patterns": [
            r"\bAccount\s*Name\s*[:#-]?\s*([^\n\r]+)",
            r"\bA\/c\s*Name\s*[:#-]?\s*([^\n\r]+)",
            r"\bBill\s*To\s*[:#-]?\s*([^\n\r]+)",
        ],
    },
}

SUMMARY_STOP_KEYWORDS = [
    "subtotal",
    "sub total",
    "grand total",
    "amount due",
    "total amount",
    "balance due",
    "bank",
    "account number",
    "account no",
    "account name",
    "invoice no",
    "invoice number",
    "invoice date",
    "bill to",
    "ship to",
    "notes",
    "terms",
    "pay by",
    "due date",
]

TABLE_HEADER_KEYWORDS = [
    "description",
    "item",
    "qty",
    "quantity",
    "unit price",
    "price",
    "amount",
    "line total",
]

LINE_ITEM_PATTERNS = [
    re.compile(
        r"^(?P<description>.+?)\s+(?P<quantity>\d+(?:\.\d+)?)\s+"
        r"(?P<unit_price>[~%$₹]?[0-9,]+(?:\.\d{1,2})?)\s+"
        r"(?P<line_total>[~%$₹]?[0-9,]+(?:\.\d{1,2})?)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?P<description>.+?)\s+(?P<unit_price>[~%$₹]?[0-9,]+(?:\.\d{1,2})?)\s+"
        r"(?P<quantity>\d+(?:\.\d+)?)\s+"
        r"(?P<line_total>[~%$₹]?[0-9,]+(?:\.\d{1,2})?)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?P<description>.+?)\s+(?P<quantity>\d+(?:\.\d+)?)\s+"
        r"(?P<line_total>[~%$₹]?[0-9,]+(?:\.\d{1,2})?)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?P<description>.+?)\s+(?P<line_total>[~%$₹]?[0-9,]+(?:\.\d{1,2})?)$",
        re.IGNORECASE,
    ),
]


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


def normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def split_text_lines(text: str) -> list[str]:
    return [normalize_line(line) for line in normalize_text(text).split("\n") if normalize_line(line)]


def clean_value(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" :-#\t")
    return value.strip()


def extract_field(text: str, patterns: Iterable[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return clean_value(match.group(1))
    return ""


def _line_has_keywords(line: str, keywords: Sequence[str]) -> bool:
    lowered = line.lower()
    return any(keyword in lowered for keyword in keywords)


def extract_field_from_document(
    lines: list[str],
    text: str,
    labels: Sequence[str],
    patterns: Sequence[str],
    *,
    search_from_bottom: bool = False,
    lookaround: int = 2,
) -> str:
    indexed_lines = list(enumerate(lines))
    if search_from_bottom:
        indexed_lines = list(reversed(indexed_lines))

    for index, line in indexed_lines:
        if _line_has_keywords(line, labels):
            match = extract_field(line, patterns)
            if match:
                return match

            neighbor_range = range(1, lookaround + 1)
            for offset in neighbor_range:
                neighbor_index = index - offset if search_from_bottom else index + offset
                if 0 <= neighbor_index < len(lines):
                    neighbor_line = lines[neighbor_index]
                    neighbor_match = extract_field(neighbor_line, patterns)
                    if neighbor_match:
                        return neighbor_match

    return extract_field(text, patterns)


def _strip_currency_markers(value: str) -> str:
    return re.sub(r"^[~%$₹]+\s*", "", value).strip()


def _clean_line_item_description(value: str) -> str:
    cleaned = clean_value(value)
    cleaned = re.sub(r"\b(?:INR|USD|EUR|GBP|Rs\.?|₹|\$)\b", "", cleaned).strip()
    return cleaned


def parse_invoice_line_item(line: str) -> InvoiceLineItem | None:
    cleaned = normalize_line(line)
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if _line_has_keywords(lowered, SUMMARY_STOP_KEYWORDS):
        return None

    for pattern in LINE_ITEM_PATTERNS:
        match = pattern.match(cleaned)
        if not match:
            continue

        groups = match.groupdict()
        description = _clean_line_item_description(groups.get("description", ""))
        if not description:
            continue

        return InvoiceLineItem(
            description=description,
            quantity=_strip_currency_markers(groups.get("quantity", "")),
            unit_price=_strip_currency_markers(groups.get("unit_price", "")),
            tax=_strip_currency_markers(groups.get("tax", "")),
            total=_strip_currency_markers(groups.get("line_total", "")),
            raw_text=cleaned,
        )

    return None


def extract_line_items_from_lines(lines: list[str]) -> list[InvoiceLineItem]:
    start_index = 0
    for index, line in enumerate(lines):
        if sum(1 for keyword in TABLE_HEADER_KEYWORDS if keyword in line.lower()) >= 2:
            start_index = index + 1
            break

    items: list[InvoiceLineItem] = []
    for line in lines[start_index:]:
        lowered = line.lower()
        if _line_has_keywords(lowered, SUMMARY_STOP_KEYWORDS):
            break

        item = parse_invoice_line_item(line)
        if item:
            items.append(item)

    return items


def extract_invoice_data(filename: str, text: str, ocr_lines: Sequence[str] | None = None) -> InvoiceData:
    normalized_text = normalize_text(text)
    lines = [normalize_line(line) for line in (ocr_lines or split_text_lines(text))]
    lines = [line for line in lines if line]

    values = {
        field_name: extract_field_from_document(
            lines,
            normalized_text,
            spec["labels"],
            spec["patterns"],
            search_from_bottom=(field_name == "total"),
        )
        for field_name, spec in FIELD_SPECS.items()
    }

    return InvoiceData(
        filename=filename,
        invoice_number=values["invoice_number"],
        date=values["date"],
        subtotal=values["subtotal"],
        tax=values["tax"],
        total=values["total"],
        account_number=values["account_number"],
        account_name=values["account_name"],
        line_items=extract_line_items_from_lines(lines),
    )


def ocr_document(image_path: Path, cv2_module, pytesseract_module, lang: str) -> OcrDocument:
    processed = preprocess_image(image_path, cv2_module)
    text = pytesseract_module.image_to_string(processed, lang=lang, config="--psm 6")

    try:
        data = pytesseract_module.image_to_data(
            processed,
            lang=lang,
            config="--psm 6",
            output_type=pytesseract_module.Output.DICT,
        )
    except Exception:
        return OcrDocument(text=text, lines=split_text_lines(text))

    grouped: dict[tuple[int, int, int], list[tuple[int, str]]] = defaultdict(list)
    for index, word in enumerate(data.get("text", [])):
        token = normalize_line(word)
        if not token:
            continue

        try:
            confidence = float(data.get("conf", ["-1"])[index])
        except (TypeError, ValueError, IndexError):
            confidence = -1.0
        if confidence < 0:
            continue

        key = (
            int(data.get("block_num", [0])[index]),
            int(data.get("par_num", [0])[index]),
            int(data.get("line_num", [0])[index]),
        )
        grouped[key].append((int(data.get("left", [0])[index]), token))

    lines = []
    for key in sorted(grouped):
        words = grouped[key]
        words.sort(key=lambda item: item[0])
        line = normalize_line(" ".join(token for _, token in words))
        if line:
            lines.append(line)

    if not lines:
        lines = split_text_lines(text)

    return OcrDocument(text=text, lines=lines)


def ocr_image(image_path: Path, cv2_module, pytesseract_module, lang: str) -> str:
    return ocr_document(image_path, cv2_module, pytesseract_module, lang).text


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
