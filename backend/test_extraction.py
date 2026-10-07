from pathlib import Path
from app.services import ocr_service, extraction_service

uploads = Path("uploads")

files = [
    f for f in uploads.rglob("*")
    if f.is_file() and f.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg"}
]

if not files:
    print("No invoice files found in the backend/uploads folder.")
else:
    file = max(files, key=lambda f: f.stat().st_mtime)
    print("Testing file:", file)

    raw_text = ocr_service.extract_text(
        file.read_bytes(),
        file.suffix.lower()
    )

    print("\n--- ACTUAL OCR TEXT ---")
    print(raw_text)

    result = extraction_service.extract_fields(raw_text)

    print("\n--- ACTUAL PDF EXTRACTION ---")
    for field in [
        "invoice_number",
        "invoice_date",
        "due_date",
        "po_number",
        "payment_terms",
        "invoice_amount",
        "total_amount",
    ]:
        print(f"{field}: {result.get(field)}")