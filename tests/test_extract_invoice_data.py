import unittest

from main import extract_invoice_data


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


if __name__ == "__main__":
    unittest.main()
