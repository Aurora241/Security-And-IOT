from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class DetectionReport(BaseModel):
    """Script giam sat YOLOv8 (yolo_env) goi khi DA xac nhan xam nhap (tu debounce >=3 frame
    lien tiep o phia client) - khong gui tung frame tho qua day."""
    camera_id: UUID
    confidence: float
    bounding_box: Optional[dict] = None
    snapshot_base64: Optional[str] = None  # anh JPEG da encode base64, khong co prefix data:...


class DetectionResult(BaseModel):
    status: str  # "intrusion" | "ignored_not_armed" | "ignored_cooldown"
    event_id: Optional[UUID] = None


class AlarmZoneSchedule(BaseModel):
    start: str  # "HH:MM" hoac "HH:MM:SS"
    end: str


class AlarmZoneUpdate(BaseModel):
    is_armed: Optional[bool] = None
    active_schedule: Optional[AlarmZoneSchedule] = None
