from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional, Annotated
from bson import ObjectId
from pydantic import BaseModel, Field, BeforeValidator, ConfigDict

def validate_object_id(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    if not isinstance(v, str) or not ObjectId.is_valid(v):
        raise ValueError("Invalid ObjectId format")
    return v

PyObjectId = Annotated[str, BeforeValidator(validate_object_id)]

class PaymentStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"

class InvoiceCreate(BaseModel):
    client_id: str = Field(..., description="Client ID this invoice belongs to")
    quotation_id: Optional[str] = Field(None, description="Optional linked quotation ID")
    subtotal: float = Field(..., gt=0, description="Invoice subtotal amount")
    tax_amount: float = Field(0.0, ge=0.0, description="Tax amount")
    grand_total: float = Field(..., gt=0, description="Grand total including tax")
    due_date: Optional[datetime] = Field(None, description="Payment due date (defaults to 30 days if omitted)")

class InvoiceUpdate(BaseModel):
    subtotal: Optional[float] = Field(None, gt=0)
    tax_amount: Optional[float] = Field(None, ge=0.0)
    grand_total: Optional[float] = Field(None, gt=0)
    due_date: Optional[datetime] = None

class InvoiceResponse(BaseModel):
    id: PyObjectId = Field(..., alias="_id", description="MongoDB ObjectId")
    invoice_number: str
    client_id: str
    quotation_id: Optional[str] = None
    subtotal: float
    tax_amount: float
    grand_total: float
    amount_paid: float
    balance_due: float
    due_date: datetime
    payment_status: PaymentStatus
    created_at: datetime
    created_by: Optional[str] = None

    model_config = ConfigDict(
        populate_by_name=True
    )
