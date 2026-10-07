"""
The end-to-end invoice processing pipeline, run as a background task right
after upload so the HTTP request returns instantly (spec requirement: large
files must not block the app).

Flow: read file -> OCR -> field extraction -> duplicate check -> validation
-> attach/create vendor -> save -> recompute vendor risk -> notify.
"""
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.invoice import Invoice, InvoiceStatus
from app.models.audit import Notification
from app.services import ocr_service, extraction_service, validation_service, risk_service
from app.utils.storage import read_file

logger = logging.getLogger(__name__)


def process_invoice(invoice_id) -> None:
    """Runs in a background task / worker. Owns its own DB session."""
    db: Session = SessionLocal()
    try:
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            logger.error("process_invoice: invoice %s not found", invoice_id)
            return

        invoice.status = InvoiceStatus.PROCESSING
        db.commit()

        try:
            file_bytes = read_file(invoice.file_path)
            ext = Path(invoice.file_path).suffix.lower()
            raw_text, confidence = ocr_service.extract_text(file_bytes, ext)
        except Exception as e:
            logger.exception("OCR failed for invoice %s", invoice_id)
            invoice.status = InvoiceStatus.FAILED
            invoice.ocr_raw_text = f"OCR_ERROR: {e}"
            db.commit()
            _notify(db, invoice, "ocr_failed", "OCR processing failed", str(e))
            return
        
        print("DEBUG RAW OCR TEXT:\n", raw_text)
        
        extracted = extraction_service.extract_fields(raw_text)
        
        
        
        print("DEBUG PAYMENT TERMS:", repr(extracted.get("payment_terms")))
        print("DEBUG INVOICE AMOUNT:", repr(extracted.get("invoice_amount")))
        print("DEBUG PO AMOUNT:", repr(extracted.get("po_amount")))

        # duplicate check
        dup = validation_service.find_duplicate(
            db, invoice.company_id,
            extracted.get("invoice_number"),
            extracted.get("vendor_gst"),
            extracted.get("total_amount"),
        )
        flags = validation_service.validate_invoice(extracted, duplicate_invoice_id=dup.id if dup else None)

        # apply extracted fields onto the invoice row
        for field in (
            "invoice_number", "po_number", "po_amount", "invoice_date", "due_date", "delivery_date",
            "payment_terms", "vendor_name_raw", "vendor_gst", "vendor_pan", "buyer_name",
            "total_amount", "invoice_amount", "cgst", "sgst", "igst", "discount",
            "email", "phone", "bank_ifsc", "bank_account_number", "extra_fields",
        ):
            if field in extracted:
                setattr(invoice, field, extracted[field])

        invoice.ocr_raw_text = raw_text
        invoice.ocr_confidence = confidence
        invoice.is_duplicate = dup is not None
        invoice.duplicate_of_invoice_id = dup.id if dup else None
        invoice.validation_flags = flags

        # link / create vendor + delivery outcome
        if extracted.get("vendor_name_raw"):
            vendor = risk_service.get_or_create_vendor(
                db, invoice.company_id, extracted["vendor_name_raw"], extracted.get("vendor_gst")
            )
            invoice.vendor_id = vendor.id
            risk_service.record_delivery_outcome(invoice)

        if flags:
            invoice.status = InvoiceStatus.FLAGGED
        elif confidence < 0.5:
            invoice.status = InvoiceStatus.NEEDS_REVIEW
        else:
            invoice.status = InvoiceStatus.PROCESSED

        db.commit()

        if invoice.vendor_id:
            db.refresh(invoice)
            vendor = invoice.vendor
            risk_service.recalculate_vendor_risk(db, vendor)
            if vendor.risk_status.value != "normal":
                _notify(db, invoice, "risk_vendor_detected",
                        f"Vendor '{vendor.name}' flagged as {vendor.risk_status.value}",
                        f"{vendor.delayed_deliveries} delayed deliveries out of {vendor.total_orders} orders.")

        if invoice.is_duplicate:
            _notify(db, invoice, "duplicate_invoice", "Duplicate invoice detected", f"Invoice {invoice.invoice_number}")

        _notify(db, invoice, "invoice_processed", "Invoice processed", f"Invoice {invoice.invoice_number or invoice.original_filename} finished processing.")

    finally:
        db.close()


def _notify(db: Session, invoice: Invoice, ntype: str, title: str, message: str) -> None:
    db.add(Notification(
        company_id=invoice.company_id,
        user_id=invoice.uploaded_by,
        type=ntype,
        title=title,
        message=message,
    ))
    db.commit()
