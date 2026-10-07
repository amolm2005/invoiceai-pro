"""
InvoiceAI Pro - invoice field extraction service.

Rule-based invoice field extraction with support for:
- labels and values on the same line
- labels on one line and corresponding values on the next line
- values stopping at nearby field labels
- explicit PO number and PO amount labels
- preserving output keys used by the existing application

Review missing or low-confidence fields before using invoice data.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------

GST_REGEX = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b", re.I)
PAN_REGEX = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.I)
EMAIL_REGEX = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_REGEX = re.compile(r"(?:\+?91[\s-]?)?[6-9]\d{9}\b")
IFSC_REGEX = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.I)

DATE_REGEX = (
    # Boundaries prevent a fragment such as "26-27/017" inside an invoice
    # number from being mistaken for a date.
    r"(?<![A-Za-z0-9/.-])(?:"
    r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}"
    r"|\d{4}[/.\-]\d{1,2}[/.\-]\d{1,2}"
    r"|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}"
    r"|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}"
    r")(?![A-Za-z0-9/.-])"
)

AMOUNT_REGEX = r"(?:INR|Rs\.?|₹|USD|\$)?\s*([\-]?\d[\d,]*(?:\.\d{1,2})?)"

DATE_FORMATS = [
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%d/%m/%y", "%d-%m-%y", "%d.%m.%y",
    "%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y",
    "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
    "%B %d, %Y", "%b %d, %Y",
    "%B %d %Y", "%b %d %Y",
    "%d %B %Y", "%d %b %Y",
]

FIELD_BOUNDARY = (
    r"invoice\s*(?:number|no\.?|#)|"
    r"invoice\s*date|"
    r"due\s*date|payment\s*due\s*date|"
    r"delivery\s*date|"
    r"payment\s*terms?|terms\s*of\s*payment|credit\s*terms?|"
    r"place\s*of\s*supply|"
    r"purchase\s*order(?:\s*(?:number|no\.?|#))?|"
    r"po\s*(?:number|no\.?|#|amount|value)|"
    r"vendor\s*name|seller(?:\s*name)?|buyer(?:\s*name)?|customer(?:\s*name)?|"
    r"bill\s*to|ship\s*to|gstin|gst\s*no\.?|"
    r"sub\s*total|subtotal|invoice\s*amount|"
    r"grand\s*total|total\s*amount|total\s*due|net\s*amount|"
    r"cgst|sgst|igst|discount|taxable\s*value|"
    r"bank\s*details|authorized\s*signatory"
)

STOP_WORDS = {
    "payment", "terms", "date", "invoice", "number", "no", "amount",
    "value", "place", "supply", "gstin", "subtotal", "total", "due",
    "bill", "ship", "vendor", "seller", "buyer", "customer", "not",
    "applicable", "n/a", "na",
}


# ---------------------------------------------------------------------
# Normalization and parsing helpers
# ---------------------------------------------------------------------

def _clean_text(text: str) -> str:
    """Normalize whitespace while retaining line boundaries."""
    text = (text or "").replace("\x0c", "\n").replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _flat_text(text: str) -> str:
    """Searchable version that allows labels and values across line breaks."""
    return re.sub(r"\s+", " ", _clean_text(text)).strip()


def _parse_date(raw: Optional[str]):
    if not raw:
        return None
    raw = re.sub(r"\s+", " ", raw.strip().rstrip(",."))
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    cleaned = str(raw).strip()
    cleaned = re.sub(r"^(INR|Rs\.?|₹|USD|\$)\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"[^\d,.\-]", "", cleaned).replace(",", "")
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _clean_field(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", str(value)).strip(" \t\r\n:;,-")
    return value or None


def _first_match(patterns: List[str], text: str) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return None


def _extract_labeled_date(text: str, label: str):
    pattern = rf"\b(?:{label})\b\s*[:#\-]?\s*({DATE_REGEX})"
    return _parse_date(_first_match([pattern], _flat_text(text)))


def _extract_labeled_amount(text: str, label: str) -> Optional[float]:
    pattern = rf"\b(?:{label})\b\s*[:#\-]?\s*{AMOUNT_REGEX}"
    return _parse_amount(_first_match([pattern], _flat_text(text)))


def _extract_label_value(
    text: str,
    label_pattern: str,
    value_pattern: str,
    *,
    boundaries: str = FIELD_BOUNDARY,
) -> Optional[str]:
    """Extract a labeled value without swallowing the next field label."""
    flat = _flat_text(text)
    pattern = (
        rf"\b(?:{label_pattern})\b\s*[:#\-]?\s*"
        rf"({value_pattern})"
        rf"(?=\s+(?:{boundaries})\b|$)"
    )
    return _clean_field(_first_match([pattern], flat))

def _extract_token_after_label(
    text: str,
    label_pattern: str
) -> Optional[str]:
    """
    Extract a token after a label.

    Supports:
    1. Label and value on the same line.
    2. Label and value on the next line.
    3. Existing flattened-text extraction as a fallback.
    """

    token = r"[A-Za-z0-9][A-Za-z0-9./\_-]*"

    # First: existing extraction logic
    value = _extract_label_value(text, label_pattern, token)

    if value:
        value = value.strip(".,;:")
        if value.lower() not in STOP_WORDS:
            return value

    # Second: line-by-line extraction
    lines = _clean_text(text).splitlines()

    label_re = re.compile(
        rf"^\s*(?:{label_pattern})\s*(?:[:#-]\s*)?(.*)$",
        re.I,
    )

    for index, line in enumerate(lines):
        match = label_re.match(line.strip())

        if not match:
            continue

        # Label + value on the same line
        same_line = match.group(1).strip()

        if same_line:
            token_match = re.match(token, same_line)

            if token_match:
                candidate = token_match.group(0).strip(".,;:")

                if candidate.lower() not in STOP_WORDS:
                    return candidate

        # Label on one line, value on next line
        if index + 1 < len(lines):
            next_line = lines[index + 1].strip()

            if next_line:
                token_match = re.match(token, next_line)

                if token_match:
                    candidate = token_match.group(0).strip(".,;:")

                    if candidate.lower() not in STOP_WORDS:
                        return candidate

    return None


def _looks_like_company_name(line: str) -> bool:
    s = line.strip()
    low = s.lower()
    if not 3 <= len(s) <= 100:
        return False
    blocked = (
        "tax invoice", "invoice", "bill to", "ship to", "gstin", "gst",
        "email", "phone", "mobile", "address", "date", "payment", "terms",
        "purchase order", "po number", "subtotal", "total", "bank details",
        "authorized signatory", "description", "place of supply",
    )
    if any(word in low for word in blocked):
        return False
    if re.search(r"\d{4,}", s) or not re.search(r"[A-Za-z]", s):
        return False
    return True


def _vendor_fallback(lines: List[str]) -> Optional[str]:
    stop_words = ("bill to", "buyer", "customer", "ship to")
    for line in lines[:20]:
        low = line.lower()
        if any(word in low for word in stop_words):
            break
        if low in {"tax invoice", "invoice", "quotation", "proforma invoice"}:
            continue
        if re.match(r"^(gstin|gst|email|phone|mobile|invoice\s+date)\b", low):
            continue
        if _looks_like_company_name(line) and ":" not in line:
            return line.strip()
    return None


def _clean_invoice_number(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip().rstrip(".,;:")
    if value.lower() in {"number", "no", "invoice", "date"}:
        return None
    return value or None
def _extract_line_labeled_value(
    lines: List[str],
    label_pattern: str,
) -> Optional[str]:
    """
    Extract a value from OCR when the label and value are:
    1. on the same line, or
    2. on the immediately following meaningful line.
    """

    label_re = re.compile(
        rf"^\s*(?:{label_pattern})\s*(?:[:#\-]?\s*)?(.*)$",
        re.I,
    )

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        match = label_re.match(line)
        if not match:
            continue

        value = match.group(1).strip(" \t:;,-")

        # Case 1: value is on the same line.
        if value:
            return value

        # Case 2: value is on the next meaningful line.
        for next_line in lines[i + 1:]:
            next_line = next_line.strip()

            if not next_line:
                continue

            # Don't take another field label as the value.
            if re.match(
                r"^(invoice\s+(?:number|no\.?|date)|"
                r"due\s+date|purchase\s+order|po\s+(?:number|no\.?|amount)|"
                r"payment\s+terms?|terms\s+of\s+payment|"
                r"place\s+of\s+supply|bill\s+to|ship\s+to)\b",
                next_line,
                re.I,
            ):
                break

            return next_line

    return None

def _extract_payment_terms(text: str) -> Optional[str]:
    """
    Extract payment terms without swallowing following invoice fields.

    Supports:
    - Payment Terms Net 30
    - Payment Terms: Net 30
    - Payment Terms
      Net 30
    """

    labels = (
        r"payment\s+terms?|"
        r"terms\s+of\s+payment|"
        r"credit\s+terms?"
    )

    # First try the existing label-based extraction.
    value_pattern = r"[A-Za-z0-9][A-Za-z0-9 ,./()\-]*"

    value = _extract_label_value(
        text,
        labels,
        value_pattern,
    )

    # Prefer the actual standard payment-term expression.
    if value:
        terms_match = re.search(
            r"\b(Net\s+\d+\s*(?:days?)?|"
            r"Due\s+on\s+receipt|"
            r"Due\s+upon\s+receipt|"
            r"Cash\s+on\s+delivery|"
            r"COD|"
            r"Advance|"
            r"Immediate|"
            r"On\s+receipt)\b",
            value,
            re.I,
        )

        if terms_match:
            return re.sub(
                r"\s+",
                " ",
                terms_match.group(0),
            ).strip()

    # Line-aware fallback.
    lines = _clean_text(text).splitlines()

    label_re = re.compile(
        rf"^\s*(?:{labels})\s*(?:[:#-]\s*)?(.*)$",
        re.I,
    )

    for index, line in enumerate(lines):
        match = label_re.match(line.strip())

        if not match:
            continue

        same_line = match.group(1).strip()

        # Value is on the same line.
        if same_line:
            terms_match = re.search(
                r"\b(Net\s+\d+\s*(?:days?)?|"
                r"Due\s+on\s+receipt|"
                r"Due\s+upon\s+receipt|"
                r"Cash\s+on\s+delivery|"
                r"COD|"
                r"Advance|"
                r"Immediate|"
                r"On\s+receipt)\b",
                same_line,
                re.I,
            )

            if terms_match:
                return re.sub(
                    r"\s+",
                    " ",
                    terms_match.group(0),
                ).strip()

        # Value is on the next line.
        if index + 1 < len(lines):
            next_line = lines[index + 1].strip()

            if next_line:
                terms_match = re.search(
                    r"\b(Net\s+\d+\s*(?:days?)?|"
                    r"Due\s+on\s+receipt|"
                    r"Due\s+upon\s+receipt|"
                    r"Cash\s+on\s+delivery|"
                    r"COD|"
                    r"Advance|"
                    r"Immediate|"
                    r"On\s+receipt)\b",
                    next_line,
                    re.I,
                )

                if terms_match:
                    return re.sub(
                        r"\s+",
                        " ",
                        terms_match.group(0),
                    ).strip()

    return None

def _extract_po_number(text: str) -> Optional[str]:
    """
    Extract PO number from common OCR layouts:
    - Purchase Order PO-123
    - Purchase Order: PO-123
    - Purchase Order
      PO-123
    - PO Number PO-123
    - PO Number
      PO-123
    """

    token = r"[A-Za-z0-9][A-Za-z0-9./_-]*"

    # Existing flattened-text patterns
    patterns = [
        rf"\bpurchase\s+order\s+(?:number|no\.?|#)\s*[:#-]?\s*({token})",
        rf"\bpo\s+(?:number|no\.?|#)\s*[:#-]?\s*({token})",
        rf"\bpurchase\s+order\s*[:#-]\s*({token})",
        rf"\bpurchase\s+order\s+({token})",
    ]

    value = _first_match(patterns, _flat_text(text))

    if value:
        value = value.strip(".,;:")

        if value.lower() not in STOP_WORDS:
            return value

    # Line-aware extraction
    lines = _clean_text(text).splitlines()

    label_re = re.compile(
        r"^\s*(?:purchase\s+order|po\s+(?:number|no\.?|#)?)"
        r"\s*(?:[:#-]\s*)?(.*)$",
        re.I,
    )

    for index, line in enumerate(lines):
        match = label_re.match(line.strip())

        if not match:
            continue

        # Value on same line
        same_line = match.group(1).strip()

        if same_line:
            token_match = re.match(token, same_line)

            if token_match:
                candidate = token_match.group(0).strip(".,;:")

                if candidate.lower() not in STOP_WORDS:
                    return candidate

        # Value on next line
        if index + 1 < len(lines):
            next_line = lines[index + 1].strip()

            if next_line:
                token_match = re.match(token, next_line)

                if token_match:
                    candidate = token_match.group(0).strip(".,;:")

                    if candidate.lower() not in STOP_WORDS:
                        return candidate

    return None

def _find_value_line(lines: List[str], required_labels: List[str]) -> Optional[str]:
    """
    Return the next non-empty OCR line after a line containing all required
    labels. This handles invoices where a row of headings is followed by a
    row of values, e.g. 'Invoice Number Invoice Date Due Date'.
    """
    for i, line in enumerate(lines[:-1]):
        if all(re.search(label, line, re.I) for label in required_labels):
            for next_line in lines[i + 1:]:
                if next_line.strip():
                    return next_line.strip()
    return None


def _extract_invoice_fields_from_header_rows(lines: List[str]) -> Dict[str, Any]:
    """Extract fields from common two-row invoice layouts."""
    found: Dict[str, Any] = {}

    # Example:
    # Invoice Number Invoice Date Due Date
    # RSI/26-27/017 30 September 2026 30 October 2026
    invoice_values = _find_value_line(
        lines,
        [r"\binvoice\s*(?:number|no\.?|#)\b", r"\binvoice\s*date\b", r"\bdue\s*date\b"],
    )
    if invoice_values:
        dates = list(re.finditer(DATE_REGEX, invoice_values, re.I))
        if dates:
            prefix = invoice_values[:dates[0].start()].strip()
            token_match = re.search(r"[A-Za-z0-9][A-Za-z0-9./_-]*", prefix)
            if token_match:
                found["invoice_number"] = _clean_invoice_number(token_match.group(0))
            found["invoice_date"] = _parse_date(dates[0].group(0))
            if len(dates) >= 2:
                found["due_date"] = _parse_date(dates[1].group(0))

    # Example:
    # Purchase Order Payment Terms Place of Supply
    # PO-PN-2087 Net 30 Maharashtra
    po_values = _find_value_line(
        lines,
        [r"\bpurchase\s*order\b", r"\bpayment\s*terms?\b", r"\bplace\s*of\s*supply\b"],
    )
    if po_values:
        po_match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9./_-]*)", po_values)
        if po_match and po_match.group(1).lower() not in STOP_WORDS:
            found["po_number"] = po_match.group(1).strip(".,;:")

        # Prefer common explicit terms such as Net 30, Net 15, COD, or due on receipt.
        terms_match = re.search(
            r"\b(Net\s+\d+\s*(?:days?)?|Due\s+on\s+receipt|Due\s+upon\s+receipt|"
            r"Cash\s+on\s+delivery|COD|Advance|Immediate|On\s+receipt)\b",
            po_values,
            re.I,
        )
        if terms_match:
            found["payment_terms"] = re.sub(r"\s+", " ", terms_match.group(0)).strip()

    return found


# ---------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------

def extract_fields(raw_text: str) -> Dict[str, Any]:
    text = _clean_text(raw_text)
    flat = _flat_text(text)
    lines = text.splitlines()
    result: Dict[str, Any] = {}

    # First try conventional inline labels.
    result["invoice_number"] = _clean_invoice_number(
        _extract_token_after_label(
            text,
            r"invoice\s*(?:number|no\.?|#)|inv\s*(?:number|no\.?|#)",
        )
    )
    
    
    result["po_number"] = _extract_po_number(text)

    result["invoice_date"] = _extract_labeled_date(flat, r"invoice\s*date")
    result["due_date"] = _extract_labeled_date(flat, r"(?:payment\s*)?due\s*date")
    result["delivery_date"] = _extract_labeled_date(flat, r"delivery\s*date")
    result["payment_terms"] = _extract_payment_terms(flat)

    result["po_amount"] = _extract_labeled_amount(
        flat, r"(?:po|purchase\s*order)\s*(?:amount|value)"
    )

    result["total_amount"] = _extract_labeled_amount(
        flat, r"(?:grand\s*total|total\s*amount|total\s*due|net\s*amount)"
    )
    result["invoice_amount"] = _extract_labeled_amount(
        flat, r"(?:sub\s*total|subtotal|invoice\s*amount)"
    )
    result["cgst"] = _extract_labeled_amount(flat, r"cgst(?:\s*\([^)]*\))?")
    result["sgst"] = _extract_labeled_amount(flat, r"sgst(?:\s*\([^)]*\))?")
    result["igst"] = _extract_labeled_amount(flat, r"igst(?:\s*\([^)]*\))?")
    result["discount"] = _extract_labeled_amount(flat, r"discount")

    # If labels and values are on separate rows, use row-aware extraction.
    row_fields = _extract_invoice_fields_from_header_rows(lines)
    for field in ("invoice_number", "invoice_date", "due_date", "po_number", "payment_terms"):
        # When a matching header row is found, its aligned value row is more
        # reliable than a generic inline-label match that may capture a label.
        if row_fields.get(field) not in (None, ""):
            result[field] = row_fields[field]

    # Explicit vendor/seller label, then conservative header fallback.
    result["vendor_name_raw"] = _extract_label_value(
        flat,
        r"vendor\s*name|seller(?:\s*name)?|from",
        r"[A-Za-z][A-Za-z0-9 &.,'()/-]{1,100}?",
    )
    if not result["vendor_name_raw"]:
        result["vendor_name_raw"] = _vendor_fallback(lines)

    result["buyer_name"] = _extract_label_value(
        flat,
        r"bill\s*to(?:\s*name)?|buyer(?:\s*name)?|customer(?:\s*name)?",
        r"[A-Za-z][A-Za-z0-9 &.,'()/-]{1,100}?",
    )

    gst_match = GST_REGEX.search(flat.upper())
    result["vendor_gst"] = gst_match.group(0).upper() if gst_match else None

    pan_match = PAN_REGEX.search(flat.upper())
    result["vendor_pan"] = pan_match.group(0).upper() if pan_match else None

    email_match = EMAIL_REGEX.search(flat)
    result["email"] = email_match.group(0) if email_match else None

    phone_match = PHONE_REGEX.search(flat)
    result["phone"] = phone_match.group(0) if phone_match else None

    ifsc_match = IFSC_REGEX.search(flat.upper())
    result["bank_ifsc"] = ifsc_match.group(0).upper() if ifsc_match else None

    account_match = re.search(
        r"\baccount\s*(?:no\.?|number)?\s*[:#\-]?\s*(\d{9,18})\b",
        flat,
        re.I,
    )
    result["bank_account_number"] = account_match.group(1) if account_match else None

    # Preserve unrecognized explicitly labeled fields for existing UI usage.
    known_labels = {
        "invoice_number", "po_number", "po_amount", "invoice_date", "due_date",
        "delivery_date", "payment_terms", "vendor_name_raw", "buyer_name",
        "total_amount", "invoice_amount", "cgst", "sgst", "igst", "discount",
        "vendor_gst", "vendor_pan", "email", "phone", "bank_ifsc",
        "bank_account_number",
    }
    extra: Dict[str, str] = {}
    for line in lines:
        match = re.match(
            r"^([A-Za-z][A-Za-z0-9 /&().\-]{2,40})\s*[:\-]\s*(.+)$",
            line,
        )
        if not match:
            continue
        label = re.sub(r"\s+", "_", match.group(1).strip().lower())
        value = match.group(2).strip()
        if label not in known_labels:
            extra[label] = value
    result["extra_fields"] = extra or None

    return result


# ---------------------------------------------------------------------
# Field completeness
# ---------------------------------------------------------------------

def compute_field_completeness(
    extracted: Dict[str, Any],
    required_fields: List[str],
) -> float:
    if not required_fields:
        return 1.0
    found = sum(
        1
        for field in required_fields
        if extracted.get(field) is not None and extracted.get(field) != ""
    )
    return found / len(required_fields)
