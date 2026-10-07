"""
Run with: python -m app.db.seed_data
Creates a demo company, admin user, a few vendors with different risk
profiles, and sample invoices - useful for your project demo/viva so the
dashboard isn't empty on first run.
"""
from datetime import date, timedelta

from app.core.database import SessionLocal, Base, engine
from app.core.security import hash_password
from app.models.company import Company, User, UserRole
from app.models.vendor import Vendor, RiskStatus
from app.models.invoice import Invoice, InvoiceStatus


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Company).filter(Company.email == "demo@invoiceai.test").first():
            print("Demo data already exists, skipping.")
            return

        company = Company(name="Acme Manufacturing Pvt Ltd", email="demo@invoiceai.test")
        db.add(company)
        db.flush()

        admin = User(
            company_id=company.id,
            full_name="Demo Admin",
            email="admin@acme.test",
            password_hash=hash_password("Demo@1234"),
            role=UserRole.COMPANY_ADMIN,
            is_email_verified=True,
        )
        employee = User(
            company_id=company.id,
            full_name="Demo Employee",
            email="employee@acme.test",
            password_hash=hash_password("Demo@1234"),
            role=UserRole.EMPLOYEE,
            is_email_verified=True,
        )
        db.add_all([admin, employee])
        db.flush()

        good_vendor = Vendor(
            company_id=company.id, name="Reliable Steel Supplies", gst_number="27AAAPL1234C1Z5",
            total_orders=12, delivered_on_time=12, delayed_deliveries=0,
            risk_score=5.0, reliability_score=95.0, risk_status=RiskStatus.NORMAL,
            total_invoice_value=450000,
        )
        medium_vendor = Vendor(
            company_id=company.id, name="Fastline Logistics", gst_number="29BBBPL5678D1Z2",
            total_orders=10, delivered_on_time=8, delayed_deliveries=2, average_delay_days=4,
            risk_score=42.0, reliability_score=58.0, risk_status=RiskStatus.MEDIUM_RISK,
            total_invoice_value=210000,
        )
        risky_vendor = Vendor(
            company_id=company.id, name="QuickPack Traders", gst_number="19CCCPL9012E1Z9",
            total_orders=8, delivered_on_time=3, delayed_deliveries=5, average_delay_days=9,
            risk_score=78.0, reliability_score=22.0, risk_status=RiskStatus.HIGH_RISK,
            total_invoice_value=95000,
        )
        db.add_all([good_vendor, medium_vendor, risky_vendor])
        db.flush()

        sample_invoices = [
            Invoice(
                company_id=company.id, vendor_id=good_vendor.id, uploaded_by=admin.id,
                file_path="/app/uploads/seed/sample1.pdf", original_filename="sample1.pdf", file_type=".pdf",
                invoice_number="INV-1001", vendor_name_raw=good_vendor.name, vendor_gst=good_vendor.gst_number,
                invoice_date=date.today() - timedelta(days=20), due_date=date.today() - timedelta(days=10),
                delivery_date=date.today() - timedelta(days=11),
                total_amount=125000, currency="INR", status=InvoiceStatus.PROCESSED,
                was_delivered_on_time=True, ocr_confidence=0.94,
            ),
            Invoice(
                company_id=company.id, vendor_id=risky_vendor.id, uploaded_by=employee.id,
                file_path="/app/uploads/seed/sample2.pdf", original_filename="sample2.pdf", file_type=".pdf",
                invoice_number="INV-1002", vendor_name_raw=risky_vendor.name, vendor_gst=risky_vendor.gst_number,
                invoice_date=date.today() - timedelta(days=15), due_date=date.today() - timedelta(days=5),
                delivery_date=date.today() + timedelta(days=2),
                total_amount=32000, currency="INR", status=InvoiceStatus.FLAGGED,
                validation_flags=[{"code": "MISSING_FIELDS", "message": "Missing required fields: po_number"}],
                was_delivered_on_time=False, delay_days=7, ocr_confidence=0.61,
            ),
        ]
        db.add_all(sample_invoices)
        db.commit()

        print("Seed data created.")
        print("Login with: admin@acme.test / Demo@1234")

    finally:
        db.close()


if __name__ == "__main__":
    run()
