from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.supabase_client import get_supabase
from app.models.alarm import AlarmZoneUpdate, DetectionReport, DetectionResult
from app.services import access_control, alarm_control, audit_log

router = APIRouter(prefix="/alarm", tags=["alarm"])


def _validate_schedule_range(start: str, end: str) -> None:
    try:
        access_control.parse_time(start)
        access_control.parse_time(end)
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="active_schedule.start/end phai dang HH:MM")
    # Khung gio cam duoc PHEP vat qua nua dem (vd 20:00-07:00, xu ly rieng trong
    # alarm_control._time_in_forbidden_window) nen KHONG kiem tra start < end nhu access_policies.


@router.post("/detections", response_model=DetectionResult)
def report_detection(payload: DetectionReport):
    """Script giam sat YOLOv8 (yolo_env, chay lien tuc rieng) goi endpoint nay SAU KHI da tu
    debounce (>=3 frame lien tiep phat hien nguoi) - backend chi lo phan enforcement (dung
    gio/zone armed hay khong, chong spam), KHONG nhan tung frame tho qua API nay."""
    snapshot_path = None
    if payload.snapshot_base64:
        snapshot_path = alarm_control.save_snapshot(str(payload.camera_id), payload.snapshot_base64)

    result = alarm_control.evaluate_detection(
        camera_id=str(payload.camera_id),
        confidence=payload.confidence,
        bounding_box=payload.bounding_box,
        snapshot_path=snapshot_path,
    )
    event_id = result["event"]["id"] if result["event"] else None
    return DetectionResult(status=result["status"], event_id=event_id)


@router.get("/events")
def list_alarm_events(limit: int = 50):
    # cameras(name, location): PostgREST tu dong embed theo FK alarm_events.camera_id ->
    # cameras.id da khai bao trong schema, khong can viet join thu cong.
    result = (
        get_supabase()
        .table("alarm_events")
        .select("id, event_type, confidence, status, snapshot_url, detected_at, cameras(name, location)")
        .order("detected_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


@router.get("/zones")
def list_alarm_zones():
    result = get_supabase().table("alarm_zones").select("*").execute()
    return result.data


@router.patch("/zones/{zone_id}")
def update_alarm_zone(zone_id: UUID, payload: AlarmZoneUpdate):
    update_data = payload.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Khong co truong nao de cap nhat")

    if "active_schedule" in update_data:
        _validate_schedule_range(update_data["active_schedule"]["start"], update_data["active_schedule"]["end"])

    result = (
        get_supabase()
        .table("alarm_zones")
        .update(update_data)
        .eq("id", str(zone_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Khong tim thay alarm_zone")

    zone = result.data[0]
    audit_log.log_action(
        action="update_alarm_zone",
        target_type="alarm_zone",
        target_id=zone["id"],
        detail=update_data,
    )
    return zone


@router.patch("/events/{event_id}/acknowledge")
def acknowledge_event(event_id: UUID):
    result = (
        get_supabase()
        .table("alarm_events")
        .update({
            "status": "acknowledged",
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", str(event_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Khong tim thay alarm_event")
    return result.data[0]
