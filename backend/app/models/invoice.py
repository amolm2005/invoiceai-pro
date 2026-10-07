import uuid
import enum
from datetime import datetime

from sqlalchemy import Column, String, Integer, Float, DateTime, Date, Enum, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class InvoiceStatus(str, enum.Enum):
    UPLOADED = "uploaded"        # file saved, waiting for OCR
    PROCESSING = "processing"    # OCR worker running
    PROCESSED = "processed"      # OCR done, fields extracted
    NEEDS_REVIEW = "needs_review"  # low confidence / missing fields
    FLAGGED = "flagged"          # validation found problems (dup, bad GST, etc.)
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"            # OCR failed


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=True, index=True)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # --- File info ---
    file_path = Column(String(500), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(16), nullable=False)

    # --- Extracted core fields ---
    invoice_number = Column(String(100), nullable=True, index=True)
    po_amount = Column(Float, nullable=True)
    po_number = Column(String(100), nullable=True)
    invoice_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    delivery_date = Column(Date, nullable=True)
    payment_terms = Column(String(255), nullable=True)

    vendor_name_raw = Column(String(255), nullable=True)
    vendor_gst = Column(String(32), nullable=True, index=True)
    vendor_pan = Column(String(16), nullable=True)
    vendor_address = Column(Text, nullable=True)

    buyer_name = Column(String(255), nullable=True)
    billing_address = Column(Text, nullable=True)
    shipping_address = Column(Text, nullable=True)

    currency = Column(String(8), default="INR", nullable=False)
    invoice_amount = Column(Float, nullable=True)
    cgst = Column(Float, nullable=True)
    sgst = Column(Float, nullable=True)
    igst = Column(Float, nullable=True)
    discount = Column(Float, nullable=True)
    total_amount = Column(Float, nullable=True, index=True)

    email = Column(String(255), nullable=True)
    phone = Column(String(32), nullable=True)
    bank_account_number = Column(String(64), nullable=True)
    bank_ifsc = Column(String(16), nullable=True)

    # Anything the OCR/extraction pipeline finds that has no dedicated column
    extra_fields = Column(JSONB, nullable=True)
    ocr_raw_text = Column(Text, nullable=True)
    ocr_confidence = Column(Float, nullable=True)  # 0-1

    # --- Status / validation ---
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.UPLOADED, nullable=False, index=True)
    is_duplicate = Column(Boolean, default=False, nullable=False)
    duplicate_of_invoice_id = Column(UUID(as_uuid=True), nullable=True)
    validation_flags = Column(JSONB, nullable=True)  # list of {code, message}

    # --- Delivery performance (feeds vendor risk engine) ---
    was_delivered_on_time = Column(Boolean, nullable=True)  # null = unknown/not yet due
    delay_days = Column(Integer, nullable=True)

    department = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    company = relationship("Company", back_populates="invoices")
    vendor = relationship("Vendor", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False, index=True)

    description = Column(String(500), nullable=True)
    hsn_code = Column(String(32), nullable=True)
    quantity = Column(Float, nullable=True)
    unit_price = Column(Float, nullable=True)
    amount = Column(Float, nullable=True)

    invoice = relationship("Invoice", back_populates="items")
