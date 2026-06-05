from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from invoice_data_extractor.extractor import (
    InvoiceData,
    configure_tesseract,
    discover_images,
    extract_invoice_data,
    import_runtime_dependencies,
    ocr_image,
    write_workbook,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract invoice fields from image files with OCR and export them to Excel."
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
        help="Excel output path. Defaults to extracted_invoice_data_<timestamp>.xlsx.",
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
    return Path(f"extracted_invoice_data_{timestamp}.xlsx")


def write_debug_text(output_path: Path, image_path: Path, text: str) -> None:
    debug_dir = output_path.with_name(f"{output_path.stem}_ocr_text")
    debug_dir.mkdir(parents=True, exist_ok=True)
    debug_file = debug_dir / f"{image_path.stem}.txt"
    debug_file.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_path = build_output_path(args.output).expanduser().resolve()

    try:
        cv2_module, pytesseract_module, Workbook, Alignment, Font = import_runtime_dependencies()
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

    for image_path in image_paths:
        print(f"Processing {image_path}")
        try:
            text = ocr_image(image_path, cv2_module, pytesseract_module, args.lang)
            if args.debug_text:
                write_debug_text(output_path, image_path, text)
            extracted_rows.append(extract_invoice_data(image_path.name, text))
        except Exception as exc:
            failures.append((image_path, str(exc)))
            extracted_rows.append(InvoiceData(filename=image_path.name))

    write_workbook(extracted_rows, output_path, (Workbook, Alignment, Font))

    print(f"Saved {len(extracted_rows)} invoice rows to {output_path}")
    if failures:
        print("Some files could not be processed:", file=sys.stderr)
        for image_path, error in failures:
            print(f"- {image_path}: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
