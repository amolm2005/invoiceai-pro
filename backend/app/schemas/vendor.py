import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class VendorOut(BaseModel):
    id: uuid.UUID
    name: str
    gst_number: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    total_orders: int
    delivered_on_time: int
    delayed_deliveries: int
    average_delay_days: float
    total_invoice_value: float
    risk_score: float
    reliability_score: float
    risk_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class VendorRiskLogOut(BaseModel):
    id: uuid.UUID
    reason: str
    risk_level: str
    details: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class VendorDetailOut(VendorOut):
    risk_logs: List[VendorRiskLogOut] = []
