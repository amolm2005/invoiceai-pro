"""
Vendor Risk Intelligence engine.

Rule (as specified):
  1 delayed delivery   -> Normal
  2 delayed deliveries -> Medium Risk
  3+ delayed deliveries -> High Risk

Also maintains the rolling aggregates (orders, on-time count, average delay,
total invoice value) and writes a VendorRiskLog entry whenever the vendor's
risk_status changes, with a human-readable reason.
"""
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.vendor import Vendor, VendorRiskLog, RiskStatus
from app.models.invoice import Invoice


def get_or_create_vendor(db: Session, company_id, name: str, gst_number: Optional[str] = None) -> Vendor:
    query = db.query(Vendor).filter(Vendor.company_id == company_id, Vendor.name == name)
    if gst_number:
        query = query.filter(Vendor.gst_number == gst_number)
    vendor = query.first()
    if vendor:
        return vendor

    vendor = Vendor(company_id=company_id, name=name, gst_number=gst_number)
    db.add(vendor)
    db.flush()
    return vendor


def record_delivery_outcome(invoice: Invoice) -> None:
    """
    Determines if this invoice's delivery was on-time or delayed, using
    delivery_date vs due_date as the comparison (delivery after due date = delayed).
    Sets invoice.was_delivered_on_time / delay_days in place.
    """
    if not invoice.delivery_date or not invoice.due_date:
        invoice.was_delivered_on_time = None
        invoice.delay_days = None
        return

    delay = (invoice.delivery_date - invoice.due_date).days
    if delay <= 0:
        invoice.was_delivered_on_time = True
        invoice.delay_days = 0
    else:
        invoice.was_delivered_on_time = False
        invoice.delay_days = delay


def _risk_status_for_delay_count(delayed_count: int) -> RiskStatus:
    if delayed_count >= settings.RISK_HIGH_DELAY_COUNT:
        return RiskStatus.HIGH_RISK
    if delayed_count >= settings.RISK_MEDIUM_DELAY_COUNT:
        return RiskStatus.MEDIUM_RISK
    return RiskStatus.NORMAL


def _reason_for_status(status: RiskStatus, delayed_count: int) -> str:
    if status == RiskStatus.HIGH_RISK:
        return "Repeated Delay"
    if status == RiskStatus.MEDIUM_RISK:
        return "Late Delivery" if delayed_count == 2 else "Repeated Delay"
    return "Normal Performance"


def recalculate_vendor_risk(db: Session, vendor: Vendor) -> None:
    """Recomputes all aggregates for a vendor from its invoices and updates risk_status."""
    invoices = db.query(Invoice).filter(Invoice.vendor_id == vendor.id).all()

    total_orders = len(invoices)
    delivered_on_time = sum(1 for i in invoices if i.was_delivered_on_time is True)
    delayed = [i for i in invoices if i.was_delivered_on_time is False]
    delayed_count = len(delayed)
    average_delay = (sum(i.delay_days or 0 for i in delayed) / delayed_count) if delayed_count else 0.0
    total_value = sum(i.total_amount or 0 for i in invoices)

    old_status = vendor.risk_status
    new_status = _risk_status_for_delay_count(delayed_count)

    vendor.total_orders = total_orders
    vendor.delivered_on_time = delivered_on_time
    vendor.delayed_deliveries = delayed_count
    vendor.average_delay_days = round(average_delay, 2)
    vendor.total_invoice_value = round(total_value, 2)
    vendor.risk_status = new_status

    # risk_score: 0-100, weighted by delay frequency and severity
    delay_ratio = (delayed_count / total_orders) if total_orders else 0
    vendor.risk_score = round(min(100.0, (delay_ratio * 60) + min(average_delay, 30) * 1.3), 2)
    vendor.reliability_score = round(max(0.0, 100.0 - vendor.risk_score), 2)

    if new_status != old_status:
        reason = _reason_for_status(new_status, delayed_count)
        db.add(VendorRiskLog(
            vendor_id=vendor.id,
            reason=reason,
            risk_level=new_status,
            details=(
                f"Vendor moved from {old_status.value if old_status else 'n/a'} to {new_status.value}. "
                f"Delayed deliveries: {delayed_count}, average delay: {vendor.average_delay_days} days."
            ),
        ))

    db.commit()
