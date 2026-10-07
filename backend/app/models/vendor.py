import uuid
import enum
from datetime import datetime

from sqlalchemy import Column, String, Integer, Float, DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class RiskStatus(str, enum.Enum):
    NORMAL = "normal"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)

    name = Column(String(255), nullable=False, index=True)
    gst_number = Column(String(32), nullable=True, index=True)
    pan_number = Column(String(16), nullable=True)
    address = Column(Text, nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(32), nullable=True)

    # --- Performance / risk aggregates (recomputed by risk_service) ---
    total_orders = Column(Integer, default=0, nullable=False)
    delivered_on_time = Column(Integer, default=0, nullable=False)
    delayed_deliveries = Column(Integer, default=0, nullable=False)
    average_delay_days = Column(Float, default=0.0, nullable=False)
    total_invoice_value = Column(Float, default=0.0, nullable=False)

    risk_score = Column(Float, default=0.0, nullable=False)          # 0 (safe) - 100 (very risky)
    reliability_score = Column(Float, default=100.0, nullable=False)  # 100 (perfect) - 0
    risk_status = Column(Enum(RiskStatus), default=RiskStatus.NORMAL, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    company = relationship("Company", back_populates="vendors")
    invoices = relationship("Invoice", back_populates="vendor")
    risk_logs = relationship("VendorRiskLog", back_populates="vendor", cascade="all, delete-orphan")


class VendorRiskLog(Base):
    """Audit trail of why a vendor's risk status changed."""
    __tablename__ = "vendor_risk_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False, index=True)
    reason = Column(String(255), nullable=False)  # e.g. "Late Delivery", "Repeated Delay"
    risk_level = Column(Enum(RiskStatus), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    vendor = relationship("Vendor", back_populates="risk_logs")
