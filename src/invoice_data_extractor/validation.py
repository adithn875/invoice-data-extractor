from __future__ import annotations

from decimal import Decimal, InvalidOperation

from invoice_data_extractor.extractor import InvoiceData, InvoiceLineItem


def _parse_decimal(value: str) -> Decimal | None:
    cleaned = value.strip().replace(",", "")
    cleaned = cleaned.lstrip("$₹")
    cleaned = cleaned.replace("INR", "").replace("Rs.", "").replace("Rs", "")
    cleaned = cleaned.strip()
    if not cleaned:
        return None
    if cleaned.endswith("%"):
        cleaned = cleaned[:-1].strip()
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _line_total_sum(line_items: list[InvoiceLineItem]) -> Decimal | None:
    totals: list[Decimal] = []
    for item in line_items:
        parsed = _parse_decimal(item.total)
        if parsed is not None:
            totals.append(parsed)
    if not totals:
        return None
    return sum(totals)


def validate_invoice(invoice: InvoiceData) -> list[str]:
    issues: list[str] = []

    subtotal = _parse_decimal(invoice.subtotal)
    tax_value = invoice.tax.strip()
    total = _parse_decimal(invoice.total)

    expected_total: Decimal | None = None
    if subtotal is not None:
        if tax_value.endswith("%"):
            pct = _parse_decimal(tax_value)
            if pct is not None:
                expected_total = subtotal + (subtotal * pct / Decimal("100"))
            else:
                issues.append(f"Could not parse tax percentage: {invoice.tax}")
        elif tax_value:
            tax_amount = _parse_decimal(tax_value)
            if tax_amount is not None:
                expected_total = subtotal + tax_amount
            else:
                issues.append(f"Could not parse tax amount: {invoice.tax}")
        else:
            expected_total = subtotal

        if total is not None and expected_total is not None:
            delta = abs(expected_total - total)
            if delta > Decimal("0.01"):
                issues.append(
                    f"Subtotal/tax does not match total. Expected {expected_total}, got {total}."
                )

    line_total_sum = _line_total_sum(invoice.line_items)
    if subtotal is not None and line_total_sum is not None:
        delta = abs(subtotal - line_total_sum)
        if delta > Decimal("0.01"):
            issues.append(
                f"Line-item totals do not match subtotal. Expected {subtotal}, got {line_total_sum}."
            )

    if invoice.total and total is None:
        issues.append(f"Total could not be parsed: {invoice.total}")

    return issues


def apply_validation(invoice: InvoiceData) -> InvoiceData:
    invoice.validation_issues = validate_invoice(invoice)
    invoice.validation_status = "passed" if not invoice.validation_issues else "failed"
    return invoice
