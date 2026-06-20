from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional, Dict, Annotated
from bson import ObjectId
from pydantic import BaseModel, Field, BeforeValidator, ConfigDict

def validate_object_id(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    if not isinstance(v, str) or not ObjectId.is_valid(v):
        raise ValueError("Invalid ObjectId format")
    return v

PyObjectId = Annotated[str, BeforeValidator(validate_object_id)]

class ProposalStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

class Milestone(BaseModel):
    title: str = Field(..., description="Milestone title")
    description: Optional[str] = Field(None, description="Detailed description of the milestone")
    due_date: Optional[str] = Field(None, description="Expected date or timeline for the milestone")

class PricingDetails(BaseModel):
    amount: float = Field(..., gt=0, description="Base proposal amount")
    currency: str = Field("USD", description="Currency code (e.g. USD, EUR, INR)")
    billing_type: str = Field("fixed", description="Billing model (e.g. fixed, hourly, milestone-based)")
    details: Optional[str] = Field(None, description="Any payment terms or additional pricing information")

class ActivityLogEntry(BaseModel):
    action: str = Field(..., description="Action name (e.g. 'created', 'updated', 'status_changed')")
    performed_by: str = Field(..., description="User ID who performed the action")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Time of the action")
    details: Optional[str] = Field(None, description="Details or comments associated with the action")

class ProposalVersionSnapshot(BaseModel):
    version: int
    title: str
    scope_of_work: str
    pricing_details: PricingDetails
    deliverables: List[str]
    timeline_milestones: List[Milestone]
    updated_at: datetime
    updated_by: str

class ProposalCreate(BaseModel):
    client_id: str = Field(..., description="ID of the client this proposal is for")
    title: str = Field(..., min_length=3, max_length=150, description="Proposal title")
    scope_of_work: str = Field(..., description="Detailed scope of work")
    pricing_details: PricingDetails = Field(..., description="Financial details of the proposal")
    deliverables: List[str] = Field(default_factory=list, description="Array of deliverables")
    timeline_milestones: List[Milestone] = Field(default_factory=list, description="Array of milestones")

class ProposalUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=150)
    scope_of_work: Optional[str] = None
    pricing_details: Optional[PricingDetails] = None
    deliverables: Optional[List[str]] = None
    timeline_milestones: Optional[List[Milestone]] = None

class ProposalResponse(BaseModel):
    id: PyObjectId = Field(..., alias="_id", description="MongoDB ObjectId")
    client_id: str
    title: str
    scope_of_work: str
    pricing_details: PricingDetails
    deliverables: List[str]
    timeline_milestones: List[Milestone]
    status: ProposalStatus
    version: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    activity_log: List[ActivityLogEntry] = Field(default_factory=list)
    version_history: List[ProposalVersionSnapshot] = Field(default_factory=list)

    model_config = ConfigDict(
        populate_by_name=True
    )
