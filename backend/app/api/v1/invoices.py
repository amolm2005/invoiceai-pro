import io
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session
import openpyxl

from app.core.database import get_db
from app.core.deps import get_current_user, get_tenant_id
from app.models.company import User
from app.models.invoice import Invoice, InvoiceStatus
from app.schemas.invoice import InvoiceOut, PaginatedInvoices, InvoiceUpdateRequest
from app.services.invoice_pipeline import process_invoice
from app.utils.storage import validate_upload, save_file

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post("/upload", response_model=InvoiceOut, status_code=201)
def upload_invoice(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: uuid.UUID = Depends(get_tenant_id),
):
    content = file.file.read()
    ext = validate_upload(file, content)
    path = save_file(company_id, content, ext)

    invoice = Invoice(
        company_id=company_id,
        uploaded_by=current_user.id,
        file_path=path,
        original_filename=file.filename,
        file_type=ext,
        status=InvoiceStatus.UPLOADED,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    # Non-blocking: OCR/extraction/validation/risk-scoring happens after the response returns
    background_tasks.add_task(process_invoice, invoice.id)

    return invoice


@router.get("", response_model=PaginatedInvoices)
def list_invoices(
    db: Session = Depends(get_db),
    company_id: uuid.UUID = Depends(get_tenant_id),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    search: Optional[str] = Query(None, description="Matches invoice number, vendor, GST, or PO number"),
    status_filter: Optional[str] = Query(None, alias="status"),
    vendor_id: Optional[uuid.UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    is_duplicate: Optional[bool] = None,
    department: Optional[str] = None,
):
    query = db.query(Invoice).filter(Invoice.company_id == company_id)

    if search:
        like = f"%{search}%"
        query = query.filter(or_(
            Invoice.invoice_number.ilike(like),
            Invoice.vendor_name_raw.ilike(like),
            Invoice.vendor_gst.ilike(like),
            Invoice.po_number.ilike(like),
        ))
    if status_filter:
        query = query.filter(Invoice.status == status_filter)
    if vendor_id:
        query = query.filter(Invoice.vendor_id == vendor_id)
    if date_from:
        query = query.filter(Invoice.invoice_date >= date_from)
    if date_to:
        query = query.filter(Invoice.invoice_date <= date_to)
    if amount_min is not None:
        query = query.filter(Invoice.total_amount >= amount_min)
    if amount_max is not None:
        query = query.filter(Invoice.total_amount <= amount_max)
    if is_duplicate is not None:
        query = query.filter(Invoice.is_duplicate == is_duplicate)
    if department:
        query = query.filter(Invoice.department == department)

    total = query.count()
    items = (
        query.order_by(Invoice.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedInvoices(total=total, page=page, page_size=page_size, items=items)


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_db), company_id: uuid.UUID = Depends(get_tenant_id)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.company_id == company_id).first()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice


@router.patch("/{invoice_id}", response_model=InvoiceOut)
def update_invoice(
    invoice_id: uuid.UUID,
    payload: InvoiceUpdateRequest,
    db: Session = Depends(get_db),
    company_id: uuid.UUID = Depends(get_tenant_id),
):
    """Human-in-the-loop correction: lets a reviewer fix any auto-extracted field."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.company_id == company_id).first()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(invoice, field, value)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/export/excel")
def export_excel(db: Session = Depends(get_db), company_id: uuid.UUID = Depends(get_tenant_id)):
    invoices = db.query(Invoice).filter(Invoice.company_id == company_id).order_by(Invoice.created_at.desc()).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Invoices"
    headers = ["Invoice Number", "Vendor", "GST", "Invoice Date", "Due Date", "Total Amount", "Status", "Duplicate"]
    ws.append(headers)
    for inv in invoices:
        ws.append([
            inv.invoice_number, inv.vendor_name_raw, inv.vendor_gst,
            str(inv.invoice_date) if inv.invoice_date else "",
            str(inv.due_date) if inv.due_date else "",
            inv.total_amount, inv.status.value, "Yes" if inv.is_duplicate else "No",
        ])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=invoices_export.xlsx"},
    )
