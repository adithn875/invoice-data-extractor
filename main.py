import os
import re
import pytesseract
import cv2
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from datetime import datetime

# ✅ Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'

# ✅ Preprocess image for better OCR results
def preprocess_image(img_path):
    image = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    image = cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    image = cv2.GaussianBlur(image, (5, 5), 0)
    _, image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return image

# ✅ Extract field using multiple regex patterns
def extract_field(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ''

# ✅ Define invoice folder path
invoice_folder = r'C:\Users\Lenovo\pythonProjectinvoiceExtractor\invoices'

# ✅ Define Excel output file path with timestamp
output_file = f"extracted_invoice_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

# ✅ Set up Excel workbook
wb = Workbook()
ws = wb.active
ws.title = 'Invoices'
headers = ['Filename', 'Invoice Number', 'Date', 'Subtotal', 'Tax', 'Account Number', 'Account Name']
ws.append(headers)

# ✅ Loop through invoice images
for filename in os.listdir(invoice_folder):
    if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        filepath = os.path.join(invoice_folder, filename)
        print(f"🔍 Processing {filepath}")

        # OCR with preprocessing
        processed = preprocess_image(filepath)
        text = pytesseract.image_to_string(processed)

        # Field extraction
        invoice_number = extract_field(text, [r'Invoice\s*#?:?\s*(\d+)', r'Invoice\s*No[:\s]*([0-9]+)'])
        date = extract_field(text, [r'Date[:\s]*(\d{2}[./-]\d{2}[./-]\d{4})', r'(\d{2}[./-]\d{2}[./-]\d{4})'])
        subtotal = extract_field(text, [r'Sub[-\s]?Total[:\s]*([\d.,]+)'])
        tax = extract_field(text, [r'Tax[:\s]*([\d.,%]+)', r'GST[:\s]*([\d.,%]+)'])
        account_number = extract_field(text, [r'Account\s*Number[:\s]*([\d ]+)', r'A/c\s*No[:\s]*([\d ]+)'])
        account_name = extract_field(text, [r'A/c\s*Name[:\s]*(.+)', r'Account\s*Name[:\s]*(.+)'])

        # Append to Excel
        ws.append([filename, invoice_number, date, subtotal, tax, account_number, account_name])

# ✅ Apply Excel formatting
for col in ws.columns:
    max_length = max(len(str(cell.value or '')) for cell in col)
    ws.column_dimensions[col[0].column_letter].width = max_length + 5

for cell in ws[1]:
    cell.font = Font(bold=True)
    cell.alignment = Alignment(horizontal='center')

# ✅ Save Excel file
wb.save(output_file)
print(f"✅ Data extraction complete. Saved to {output_file}")
