import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_tenant_id
from app.models.vendor import Vendor
from app.schemas.vendor import VendorOut, VendorDetailOut

router = APIRouter(prefix="/vendors", tags=["Vendors"])


@router.get("", response_model=List[VendorOut])
def list_vendors(
    db: Session = Depends(get_db),
    company_id: uuid.UUID = Depends(get_tenant_id),
    risk_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    query = db.query(Vendor).filter(Vendor.company_id == company_id)
    if risk_status:
        query = query.filter(Vendor.risk_status == risk_status)
    if search:
        query = query.filter(Vendor.name.ilike(f"%{search}%"))
    return query.order_by(Vendor.risk_score.desc()).all()


@router.get("/risk", response_model=List[VendorOut])
def list_risk_vendors(db: Session = Depends(get_db), company_id: uuid.UUID = Depends(get_tenant_id)):
    """Vendors currently in medium_risk or high_risk (the 'Risk Vendor section')."""
    return (
        db.query(Vendor)
        .filter(Vendor.company_id == company_id, Vendor.risk_status != "normal")
        .order_by(Vendor.risk_score.desc())
        .all()
    )


@router.get("/{vendor_id}", response_model=VendorDetailOut)
def get_vendor(vendor_id: uuid.UUID, db: Session = Depends(get_db), company_id: uuid.UUID = Depends(get_tenant_id)):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id, Vendor.company_id == company_id).first()
    if not vendor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")
    return vendor
