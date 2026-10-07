import uuid
from datetime import date, timedelta
from typing import Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_tenant_id
from app.models.invoice import Invoice, InvoiceStatus
from app.models.vendor import Vendor, RiskStatus

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db), company_id: uuid.UUID = Depends(get_tenant_id)) -> Dict[str, Any]:
    base = db.query(Invoice).filter(Invoice.company_id == company_id)
    today = date.today()

    total_invoices = base.count()
    todays_uploads = base.filter(func.date(Invoice.created_at) == today).count()
    processed = base.filter(Invoice.status == InvoiceStatus.PROCESSED).count()
    pending_review = base.filter(Invoice.status == InvoiceStatus.NEEDS_REVIEW).count()
    duplicates = base.filter(Invoice.is_duplicate == True).count()  # noqa: E712
    flagged = base.filter(Invoice.status == InvoiceStatus.FLAGGED).count()

    total_vendors = db.query(Vendor).filter(Vendor.company_id == company_id).count()
    risk_vendors = db.query(Vendor).filter(Vendor.company_id == company_id, Vendor.risk_status != RiskStatus.NORMAL).count()

    avg_confidence = db.query(func.avg(Invoice.ocr_confidence)).filter(
        Invoice.company_id == company_id, Invoice.ocr_confidence.isnot(None)
    ).scalar()

    monthly_value = db.query(func.sum(Invoice.total_amount)).filter(
        Invoice.company_id == company_id,
        Invoice.created_at >= today.replace(day=1),
    ).scalar() or 0

    status_breakdown = dict(
        db.query(Invoice.status, func.count(Invoice.id))
        .filter(Invoice.company_id == company_id)
        .group_by(Invoice.status)
        .all()
    )

    # Monthly trend - last 6 months invoice counts
    trend = []
    for i in range(5, -1, -1):
        month_start = (today.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        count = base.filter(Invoice.created_at >= month_start, Invoice.created_at < next_month).count()
        trend.append({"month": month_start.strftime("%b %Y"), "count": count})

    top_vendors = (
        db.query(Vendor)
        .filter(Vendor.company_id == company_id)
        .order_by(Vendor.total_invoice_value.desc())
        .limit(5)
        .all()
    )
    worst_vendors = (
        db.query(Vendor)
        .filter(Vendor.company_id == company_id)
        .order_by(Vendor.risk_score.desc())
        .limit(5)
        .all()
    )

    return {
        "total_invoices": total_invoices,
        "todays_uploads": todays_uploads,
        "invoices_processed": processed,
        "pending_review": pending_review,
        "duplicate_invoices": duplicates,
        "flagged_invoices": flagged,
        "total_vendors": total_vendors,
        "risk_vendors": risk_vendors,
        "ocr_accuracy": round((avg_confidence or 0) * 100, 1),
        "monthly_invoice_value": round(monthly_value, 2),
        "invoice_status_breakdown": {k.value if hasattr(k, "value") else k: v for k, v in status_breakdown.items()},
        "monthly_invoice_trend": trend,
        "top_vendors": [{"name": v.name, "value": v.total_invoice_value} for v in top_vendors],
        "worst_vendors": [{"name": v.name, "risk_score": v.risk_score, "status": v.risk_status.value} for v in worst_vendors],
    }
