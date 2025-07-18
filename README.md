# 🧾 Invoice Data Extractor (OCR to Excel)

This project automatically extracts data from invoice images using OCR and exports the results to an Excel sheet. Ideal for digitizing bulk invoice processing in businesses.

## 🔍 Features
- Extracts: Invoice Number, Date, Total Amount, etc.
- OCR via Tesseract
- Regex-based field detection
- Output as `.xlsx` file with proper formatting

## 🛠️ Tech Stack
- Python
- OpenCV
- pytesseract (OCR)
- pandas + openpyxl (Excel export)
- regex

## 🖼️ Sample Input
![sample](invoices/invoice1.jpg)

## 📦 How to Run

1. Clone the repo  
   ```bash
   git clone https://github.com/adithn875/invoice-data-extractor.git
   cd invoice-data-extractor
