from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from invoice_data_extractor.extractor import InvoiceData, InvoiceLineItem


SUMMARY_HEADERS = [
    "Filename",
    "Invoice Number",
    "Date",
    "Subtotal",
    "Tax",
    "Total",
    "Account Number",
    "Account Name",
    "Source Hash",
    "Duplicate",
    "Duplicate Reason",
    "Validation Status",
    "Validation Issues",
]

LINE_ITEM_HEADERS = [
    "Filename",
    "Invoice Number",
    "Line",
    "Description",
    "Quantity",
    "Unit Price",
    "Tax",
    "Total",
    "Raw Text",
]


def _amount_label(value: str) -> str:
    return value or ""


def invoice_summary_row(invoice: InvoiceData) -> dict[str, object]:
    return {
        "Filename": invoice.filename,
        "Invoice Number": invoice.invoice_number,
        "Date": invoice.date,
        "Subtotal": _amount_label(invoice.subtotal),
        "Tax": _amount_label(invoice.tax),
        "Total": _amount_label(invoice.total),
        "Account Number": invoice.account_number,
        "Account Name": invoice.account_name,
        "Source Hash": invoice.source_hash,
        "Duplicate": invoice.duplicate,
        "Duplicate Reason": invoice.duplicate_reason,
        "Validation Status": invoice.validation_status,
        "Validation Issues": "; ".join(invoice.validation_issues),
    }


def line_item_row(invoice: InvoiceData, item: InvoiceLineItem, index: int) -> dict[str, object]:
    return {
        "Filename": invoice.filename,
        "Invoice Number": invoice.invoice_number,
        "Line": index,
        "Description": item.description,
        "Quantity": item.quantity,
        "Unit Price": item.unit_price,
        "Tax": item.tax,
        "Total": item.total,
        "Raw Text": item.raw_text,
    }


def write_excel_export(invoices: list[InvoiceData], output_path: Path) -> list[Path]:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    output_path = output_path.with_suffix(".xlsx")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "Invoices"

    summary_sheet.append(SUMMARY_HEADERS)
    for invoice in invoices:
        summary_sheet.append(list(invoice_summary_row(invoice).values()))

    for cell in summary_sheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    for column in summary_sheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column)
        summary_sheet.column_dimensions[column[0].column_letter].width = min(max_length + 4, 45)

    line_sheet = workbook.create_sheet("Line Items")
    line_sheet.append(LINE_ITEM_HEADERS)
    for invoice in invoices:
        for index, item in enumerate(invoice.line_items, start=1):
            line_sheet.append(list(line_item_row(invoice, item, index).values()))

    for cell in line_sheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    for column in line_sheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column)
        line_sheet.column_dimensions[column[0].column_letter].width = min(max_length + 4, 45)

    workbook.save(output_path)
    return [output_path]


def write_csv_export(invoices: list[InvoiceData], output_path: Path) -> list[Path]:
    output_path = output_path.with_suffix(".csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    summary_path = output_path
    line_items_path = output_path.with_name(f"{output_path.stem}_line_items.csv")

    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_HEADERS)
        writer.writeheader()
        for invoice in invoices:
            writer.writerow(invoice_summary_row(invoice))

    with line_items_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LINE_ITEM_HEADERS)
        writer.writeheader()
        for invoice in invoices:
            for index, item in enumerate(invoice.line_items, start=1):
                writer.writerow(line_item_row(invoice, item, index))

    return [summary_path, line_items_path]


def write_json_export(invoices: list[InvoiceData], output_path: Path) -> list[Path]:
    output_path = output_path.with_suffix(".json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "invoices": [
            {
                **asdict(invoice),
                "line_items": [asdict(item) for item in invoice.line_items],
            }
            for invoice in invoices
        ]
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return [output_path]


def export_invoices(invoices: list[InvoiceData], output_path: Path, export_format: str) -> list[Path]:
    if export_format == "xlsx":
        return write_excel_export(invoices, output_path)
    if export_format == "csv":
        return write_csv_export(invoices, output_path)
    if export_format == "json":
        return write_json_export(invoices, output_path)
    raise ValueError(f"Unsupported export format: {export_format}")
