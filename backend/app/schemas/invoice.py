import uuid
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class InvoiceItemOut(BaseModel):
    id: uuid.UUID
    description: Optional[str]
    hsn_code: Optional[str]
    quantity: Optional[float]
    unit_price: Optional[float]
    amount: Optional[float]

    class Config:
        from_attributes = True


class InvoiceOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    vendor_id: Optional[uuid.UUID]
    original_filename: str
    invoice_number: Optional[str]
    po_number: Optional[str]
    invoice_date: Optional[date]
    due_date: Optional[date]
    delivery_date: Optional[date]
    vendor_name_raw: Optional[str]
    vendor_gst: Optional[str]
    total_amount: Optional[float]
    invoice_amount: Optional[float]
    cgst: Optional[float]
    sgst: Optional[float]
    igst: Optional[float]
    currency: str
    status: str
    is_duplicate: bool
    validation_flags: Optional[List[Dict[str, Any]]]
    extra_fields: Optional[Dict[str, Any]]
    ocr_confidence: Optional[float]
    created_at: datetime
    items: List[InvoiceItemOut] = []
    ocr_raw_text: Optional[str] = None
   

    class Config:
        from_attributes = True


class InvoiceListItem(BaseModel):
    """Lighter-weight shape for table/list views."""
    id: uuid.UUID
    invoice_number: Optional[str]
    po_number: Optional[str] = None
    po_amount: Optional[float] = None
    payment_terms: Optional[str] = None
    invoice_amount: Optional[float] = None
    vendor_name_raw: Optional[str]
    invoice_date: Optional[date]
    vendor_gst: Optional[str]
    due_date: Optional[date]
    ocr_raw_text: Optional[str] = None
    total_amount: Optional[float]
    status: str
    is_duplicate: bool

    class Config:
        from_attributes = True


class PaginatedInvoices(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[InvoiceListItem]


class InvoiceUpdateRequest(BaseModel):
    """Manual correction of any auto-extracted field (human-in-the-loop review)."""
    invoice_number: Optional[str] = None
    vendor_name_raw: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    delivery_date: Optional[date] = None
    total_amount: Optional[float] = None
    status: Optional[str] = None
    department: Optional[str] = None
