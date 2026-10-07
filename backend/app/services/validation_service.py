"""
Validation service: runs the rule checks listed in the spec against a
freshly-extracted invoice, before it's saved as PROCESSED.
Returns a list of {code, message} flags; an empty list means the invoice is clean.
"""
import re
from datetime import date, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.models.invoice import Invoice

GST_REGEX = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}$")
INVOICE_NUMBER_REGEX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-/_]{1,40}$")


def find_duplicate(db: Session, company_id, invoice_number: Optional[str], vendor_gst: Optional[str], total_amount: Optional[float]):
    """A duplicate = same company + same invoice_number + same vendor GST (or same amount if GST missing)."""
    if not invoice_number:
        return None
    query = db.query(Invoice).filter(
        Invoice.company_id == company_id,
        Invoice.invoice_number == invoice_number,
    )
    if vendor_gst:
        query = query.filter(Invoice.vendor_gst == vendor_gst)
    elif total_amount is not None:
        query = query.filter(Invoice.total_amount == total_amount)
    return query.first()


def validate_invoice(extracted: Dict[str, Any], duplicate_invoice_id=None) -> List[Dict[str, str]]:
    flags: List[Dict[str, str]] = []

    if duplicate_invoice_id:
        flags.append({"code": "DUPLICATE_INVOICE", "message": "Matches an already-existing invoice for this vendor."})

    required = ["invoice_number", "vendor_name_raw", "total_amount"]
    missing = [f for f in required if not extracted.get(f)]
    if missing:
        flags.append({"code": "MISSING_FIELDS", "message": f"Missing required fields: {', '.join(missing)}"})

    gst = extracted.get("vendor_gst")
    if gst and not GST_REGEX.match(gst):
        flags.append({"code": "WRONG_GST", "message": f"GST number '{gst}' does not match the expected format."})

    invoice_number = extracted.get("invoice_number")
    if invoice_number and not INVOICE_NUMBER_REGEX.match(invoice_number):
        flags.append({"code": "INVALID_INVOICE_NUMBER", "message": f"Invoice number '{invoice_number}' looks malformed."})

    invoice_date = extracted.get("invoice_date")
    if invoice_date:
        if isinstance(invoice_date, date) and invoice_date > date.today():
            flags.append({"code": "FUTURE_INVOICE_DATE", "message": "Invoice date is in the future."})
        if isinstance(invoice_date, date) and invoice_date < date.today() - timedelta(days=365 * 10):
            flags.append({"code": "WRONG_DATE_FORMAT", "message": "Invoice date looks implausibly old - check OCR parsing."})
    else:
        flags.append({"code": "WRONG_DATE_FORMAT", "message": "Could not parse a valid invoice date."})

    for amount_field in ("total_amount", "invoice_amount"):
        val = extracted.get(amount_field)
        if val is not None and val < 0:
            flags.append({"code": "NEGATIVE_AMOUNT", "message": f"{amount_field} is negative ({val})."})

    total = extracted.get("total_amount")
    if total is not None and total == 0:
        flags.append({"code": "WRONG_AMOUNT", "message": "Total amount is zero - likely an extraction error."})

    return flags
