from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from invoice_data_extractor.export import export_invoices
from invoice_data_extractor.extractor import (
    InvoiceData,
    configure_tesseract,
    discover_images,
    file_sha256,
    extract_invoice_data,
    ocr_document,
    import_runtime_dependencies,
)
from invoice_data_extractor.storage import (
    DEFAULT_DB_PATH,
    lookup_duplicate_reason,
    save_invoice_history,
)
from invoice_data_extractor.validation import apply_validation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract invoice fields from image files with OCR and export them to Excel, CSV, or JSON."
    )
    parser.add_argument(
        "-i",
        "--input",
        default="examples/invoices",
        help="Image file or directory containing invoice images. Defaults to examples/invoices.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Export output path base. Defaults to extracted_invoice_data_<timestamp>.",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=("xlsx", "csv", "json"),
        default="xlsx",
        help="Export format. Defaults to xlsx.",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="SQLite database path for invoice history. Defaults to .invoice_history.sqlite3.",
    )
    parser.add_argument("--recursive", action="store_true", help="Search directories recursively.")
    parser.add_argument(
        "--tesseract-cmd",
        default=os.environ.get("TESSERACT_CMD"),
        help="Path to the Tesseract executable. Can also be set with TESSERACT_CMD.",
    )
    parser.add_argument("--lang", default="eng", help="Tesseract language code. Defaults to eng.")
    parser.add_argument("--debug-text", action="store_true", help="Write OCR text files.")
    return parser.parse_args()


def build_output_path(output_arg: str | None) -> Path:
    if output_arg:
        return Path(output_arg)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(f"extracted_invoice_data_{timestamp}")


def write_debug_text(output_base: Path, image_path: Path, text: str) -> None:
    debug_dir = output_base.with_name(f"{output_base.stem}_ocr_text")
    debug_dir.mkdir(parents=True, exist_ok=True)
    debug_file = debug_dir / f"{image_path.stem}.txt"
    debug_file.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_base = build_output_path(args.output).expanduser().resolve()
    db_path = Path(args.db).expanduser().resolve()

    try:
        cv2_module, pytesseract_module, _, _, _ = import_runtime_dependencies()
        configure_tesseract(pytesseract_module, args.tesseract_cmd)
        image_paths = discover_images(input_path, args.recursive)
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not image_paths:
        print(f"No invoice images found in {input_path}", file=sys.stderr)
        return 1

    extracted_rows: list[InvoiceData] = []
    failures: list[tuple[Path, str]] = []
    seen_hashes: set[str] = set()
    seen_invoice_numbers: set[str] = set()

    for image_path in image_paths:
        print(f"Processing {image_path}")
        try:
            document = ocr_document(image_path, cv2_module, pytesseract_module, args.lang)
            invoice = extract_invoice_data(image_path.name, document.text, document.lines)
            invoice.source_path = str(image_path)
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

            save_invoice_history(db_path, invoice, source_path=str(image_path))

            if args.debug_text:
                write_debug_text(output_base, image_path, document.text)

            extracted_rows.append(invoice)
            seen_hashes.add(invoice.source_hash)
            if invoice.invoice_number:
                seen_invoice_numbers.add(invoice.invoice_number)
        except Exception as exc:
            failures.append((image_path, str(exc)))
            extracted_rows.append(InvoiceData(filename=image_path.name, validation_status="failed"))

    output_files = export_invoices(extracted_rows, output_base, args.format)

    print(f"Saved {len(extracted_rows)} invoice rows to {', '.join(str(path) for path in output_files)}")
    print(f"History database: {db_path}")
    if failures:
        print("Some files could not be processed:", file=sys.stderr)
        for image_path, error in failures:
            print(f"- {image_path}: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
