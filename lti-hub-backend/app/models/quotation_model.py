from datetime import datetime
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

class QuotationStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    APPROVED = "approved"
    REJECTED = "rejected"

class LineItem(BaseModel):
    description: str = Field(..., description="Line item description")
    quantity: float = Field(..., gt=0, description="Quantity")
    unit_price: float = Field(..., ge=0, description="Unit price")
    total: float = Field(0.0, description="Total cost for this item (server calculated)")

class QuotationCreate(BaseModel):
    client_id: str = Field(..., description="Client ID associated with this quotation")
    line_items: List[LineItem] = Field(..., min_length=1, description="List of line items")
    discount_percentage: float = Field(0.0, ge=0.0, le=100.0, description="Discount percentage (0-100)")
    tax_rate: float = Field(0.0, ge=0.0, le=1.0, description="Tax rate as a decimal (e.g., 0.18 for 18%)")

class QuotationUpdate(BaseModel):
    line_items: Optional[List[LineItem]] = None
    discount_percentage: Optional[float] = Field(None, ge=0.0, le=100.0)
    tax_rate: Optional[float] = Field(None, ge=0.0, le=1.0)

class QuotationResponse(BaseModel):
    id: PyObjectId = Field(..., alias="_id", description="MongoDB ObjectId")
    client_id: str
    quotation_number: str
    line_items: List[LineItem]
    subtotal: float
    discount_amount: float
    tax_amount: float
    grand_total: float
    status: QuotationStatus
    created_at: datetime

    model_config = ConfigDict(
        populate_by_name=True
    )
