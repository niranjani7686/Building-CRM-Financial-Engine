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

class ProjectStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ProjectCreate(BaseModel):
    client_id: str = Field(..., description="Client ID this project belongs to")
    name: str = Field(..., min_length=3, description="Name of the project")
    description: Optional[str] = Field(None, description="Detailed project description")
    start_date: Optional[datetime] = Field(None, description="Project start date")
    end_date: Optional[datetime] = Field(None, description="Expected project end date")
    budget: Optional[float] = Field(None, ge=0, description="Allocated budget for the project")

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3)
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    budget: Optional[float] = Field(None, ge=0)

class ProjectResponse(BaseModel):
    id: PyObjectId = Field(..., alias="_id", description="MongoDB ObjectId")
    client_id: str
    name: str
    description: Optional[str] = None
    status: ProjectStatus
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    budget: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: str

    model_config = ConfigDict(
        populate_by_name=True
    )
