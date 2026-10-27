from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class EmployeeCreate(BaseModel):
    code: str
    full_name: str
    department: Optional[str] = None
    position: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    hired_at: Optional[date] = None


class EmployeeResponse(BaseModel):
    id: UUID
    code: str
    full_name: str
    department: Optional[str] = None
    position: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Literal["active", "inactive", "suspended"]
    photo_url: Optional[str] = None
    hired_at: Optional[date] = None
    created_at: datetime
