"""
Unit tests for the core business logic (validation + risk rules).
These don't require a live database - pure function tests.
Run with: pytest tests/ -v
"""
from datetime import date, timedelta
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import validation_service, risk_service
from app.core.config import settings


def test_valid_gst_passes():
    extracted = {
        "invoice_number": "INV-001",
        "vendor_name_raw": "Test Vendor",
        "total_amount": 1000.0,
        "vendor_gst": "27AAAPL1234C1Z5",
        "invoice_date": date.today(),
    }
    flags = validation_service.validate_invoice(extracted)
    codes = [f["code"] for f in flags]
    assert "WRONG_GST" not in codes


def test_invalid_gst_flagged():
    extracted = {
        "invoice_number": "INV-001",
        "vendor_name_raw": "Test Vendor",
        "total_amount": 1000.0,
        "vendor_gst": "NOT-A-GST",
        "invoice_date": date.today(),
    }
    flags = validation_service.validate_invoice(extracted)
    codes = [f["code"] for f in flags]
    assert "WRONG_GST" in codes


def test_future_date_flagged():
    extracted = {
        "invoice_number": "INV-002",
        "vendor_name_raw": "Test Vendor",
        "total_amount": 500.0,
        "invoice_date": date.today() + timedelta(days=5),
    }
    flags = validation_service.validate_invoice(extracted)
    codes = [f["code"] for f in flags]
    assert "FUTURE_INVOICE_DATE" in codes


def test_negative_amount_flagged():
    extracted = {
        "invoice_number": "INV-003",
        "vendor_name_raw": "Test Vendor",
        "total_amount": -50.0,
        "invoice_date": date.today(),
    }
    flags = validation_service.validate_invoice(extracted)
    codes = [f["code"] for f in flags]
    assert "NEGATIVE_AMOUNT" in codes


def test_missing_required_fields_flagged():
    extracted = {"invoice_date": date.today()}
    flags = validation_service.validate_invoice(extracted)
    codes = [f["code"] for f in flags]
    assert "MISSING_FIELDS" in codes


def test_risk_status_thresholds():
    assert risk_service._risk_status_for_delay_count(0).value == "normal"
    assert risk_service._risk_status_for_delay_count(1).value == "normal"
    assert risk_service._risk_status_for_delay_count(2).value == "medium_risk"
    assert risk_service._risk_status_for_delay_count(3).value == "high_risk"
    assert risk_service._risk_status_for_delay_count(10).value == "high_risk"
