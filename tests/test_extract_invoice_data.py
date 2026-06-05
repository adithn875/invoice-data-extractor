import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invoice_data_extractor import (
    InvoiceData,
    InvoiceLineItem,
    apply_validation,
    export_invoices,
    extract_invoice_data,
    load_recent_history,
    lookup_duplicate_reason,
    save_invoice_history,
)


class ExtractInvoiceDataTest(unittest.TestCase):
    def test_extract_invoice_data_from_common_invoice_text(self):
        text = """
        Invoice No: INV-2026-001
        Invoice Date: 05/06/2026
        Account Name: Acme Services
        Account Number: 1234 5678
        Sub Total: INR 1,200.00
        GST: 216.00
        Grand Total: INR 1,416.00
        """

        row = extract_invoice_data("invoice.png", text)

        self.assertEqual(row.filename, "invoice.png")
        self.assertEqual(row.invoice_number, "INV-2026-001")
        self.assertEqual(row.date, "05/06/2026")
        self.assertEqual(row.account_name, "Acme Services")
        self.assertEqual(row.account_number, "1234 5678")
        self.assertEqual(row.subtotal, "1,200.00")
        self.assertEqual(row.tax, "216.00")
        self.assertEqual(row.total, "1,416.00")

    def test_extracts_line_items_and_validates_totals(self):
        text = """
        Invoice No: INV-77
        Invoice Date: March.06.2024
        Item Description Qty Price Total
        Brand consultation 100 1 $100
        Logo design 100 1 $100
        Subtotal $200
        Tax 10%
        Grand Total $220
        Account Name: Acme Services
        """

        row = extract_invoice_data("invoice4.png", text)
        apply_validation(row)

        self.assertGreaterEqual(len(row.line_items), 2)
        self.assertEqual(row.validation_status, "passed")
        self.assertEqual(row.line_items[0].description, "Brand consultation")

    def test_database_duplicate_detection_and_history(self):
        with tempfile.TemporaryDirectory() as temp_dir_name:
            db_path = Path(temp_dir_name) / "history.sqlite3"
            invoice = InvoiceData(
                filename="invoice.png",
                invoice_number="INV-001",
                source_hash="abc123",
                total="100.00",
                line_items=[InvoiceLineItem(description="Service", total="100.00")],
            )
            apply_validation(invoice)
            save_invoice_history(db_path, invoice, source_path="invoice.png")

            duplicate_reason = lookup_duplicate_reason(db_path, "abc123", "INV-001")
            history = load_recent_history(db_path, limit=10)

            self.assertEqual(duplicate_reason, "same_uploaded_file")
            self.assertEqual(len(history), 1)

    def test_export_formats_create_files(self):
        invoice = InvoiceData(
            filename="invoice.png",
            invoice_number="INV-001",
            total="100.00",
            validation_status="passed",
            line_items=[InvoiceLineItem(description="Service", total="100.00")],
        )
        with tempfile.TemporaryDirectory() as temp_dir_name:
            base = Path(temp_dir_name) / "export"

            csv_files = export_invoices([invoice], base, "csv")
            json_files = export_invoices([invoice], base, "json")
            xlsx_files = export_invoices([invoice], base, "xlsx")

            self.assertTrue(csv_files[0].exists())
            self.assertTrue(csv_files[1].exists())
            self.assertTrue(json_files[0].exists())
            self.assertTrue(xlsx_files[0].exists())


if __name__ == "__main__":
    unittest.main()
