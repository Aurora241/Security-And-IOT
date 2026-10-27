from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class AccessPolicyCreate(BaseModel):
    allowed_days: list[str]
    allowed_time_start: str  # "HH:MM" hoac "HH:MM:SS"
    allowed_time_end: str


class AccessPolicyUpdate(BaseModel):
    allowed_days: Optional[list[str]] = None
    allowed_time_start: Optional[str] = None
    allowed_time_end: Optional[str] = None
    is_active: Optional[bool] = None


class AccessPolicyResponse(BaseModel):
    id: UUID
    employee_id: UUID
    access_point_id: UUID
    allowed_days: list[str]
    allowed_time_start: str
    allowed_time_end: str
    is_active: bool
    created_at: datetime
