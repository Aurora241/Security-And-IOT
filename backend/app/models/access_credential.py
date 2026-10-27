from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


class AccessCredentialCreate(BaseModel):
    employee_id: UUID
    type: Literal["face", "fingerprint"]
    # Tuần 3-4: nhận credential_data trực tiếp (đã trích embedding sẵn hoặc placeholder).
    # Tuần 7-8: thay bằng upload ảnh, AI service tự trích embedding trước khi gọi hàm lưu.
    credential_data: dict[str, Any]


class FaceEnrollRequest(BaseModel):
    employee_id: UUID
    image_base64: str  # data URL ("data:image/jpeg;base64,...") hoặc base64 thô


class AccessCredentialResponse(BaseModel):
    id: UUID
    employee_id: UUID
    type: Literal["face", "fingerprint"]
    is_active: bool
    enrolled_at: datetime
