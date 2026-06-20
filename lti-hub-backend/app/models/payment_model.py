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

class PaymentMethodEnum(str, Enum):
    BANK_TRANSFER = "bank_transfer"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    UPI = "upi"
    CASH = "cash"
    CHEQUE = "cheque"
    PAYPAL = "paypal"
    OTHER = "other"

class PaymentStatusEnum(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    REFUNDED = "refunded"

class RecordPayment(BaseModel):
    invoice_id: str = Field(..., description="Invoice ID this payment is against")
    client_id: str = Field(..., description="Client ID making the payment")
    payment_amount: float = Field(..., gt=0, description="Payment amount (must be positive)")
    payment_date: Optional[datetime] = Field(None, description="Date of payment (defaults to now if omitted)")
    payment_method: PaymentMethodEnum = Field(..., description="Method of payment")
    reference_number: Optional[str] = Field(None, description="Bank/transaction reference number")

class PaymentResponse(BaseModel):
    id: PyObjectId = Field(..., alias="_id", description="MongoDB ObjectId")
    invoice_id: str
    client_id: str
    payment_amount: float
    payment_date: datetime
    payment_method: PaymentMethodEnum
    reference_number: Optional[str] = None
    status: PaymentStatusEnum
    created_at: datetime

    model_config = ConfigDict(
        populate_by_name=True
    )
