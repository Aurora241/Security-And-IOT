"""
Enforcement module Alarm - quyet dinh "xam nhap" theo kieu chuong trom co dien (Huong 1 da
chot voi user, bac bo Huong 2 phan biet nguoi la/quen vi video qua DeepFace - khong phu hop
van phong SME hiem ca dem):

    co nguoi (YOLO detect) + zone dang armed + dung khung gio cam (active_schedule)
                                    => day la 1 "xam nhap" (ghi alarm_events)

Chong bao dong gia (>=3 frame lien tiep) do script giam sat (yolo_env, chay lien tuc rieng,
giu model/camera luon mo) tu lam TRUOC khi goi sang day - ham o day chi nhan 1 "detection da
duoc xac nhan", khong nhan tung frame tho qua API (khac kieu subprocess-per-request cua
DeepFace/face_embedding.py - YOLO can real-time, khong the load lai model moi frame).

Chong spam: sau 1 alarm_event cho 1 zone, khoa COOLDOWN_SECONDS khong tao event moi, du
nguoi con dung trong khung hinh.
"""
import logging
import uuid
from base64 import b64decode
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.core.supabase_client import get_supabase
from app.services import alarm_mqtt

logger = logging.getLogger("alarm_control")

COOLDOWN_SECONDS = 60
BUZZER_DURATION_SECONDS = 10

SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "storage" / "alarm_snapshots"


def get_default_zone() -> dict:
    """He thong hien chi co 1 alarm_zone - lay dung ban ghi do. Raise ngay neu cau hinh sai
    (0 hoac >1 zone) de phat hien som, giong get_primary_access_point ben Access Control."""
    result = get_supabase().table("alarm_zones").select("*").execute()
    if not result.data:
        raise RuntimeError("Chua co alarm_zone nao trong Supabase (bang alarm_zones)")
    if len(result.data) > 1:
        raise RuntimeError("Co nhieu alarm_zone active - can chi dinh zone_id cu the, khong the tu chon")
    return result.data[0]


def get_alarm_device() -> Optional[dict]:
    """Lay thiet bi coi dien tu (devices.type='alarm_unit'). Tra ve None neu chua co thiet bi
    nao cau hinh (chua mua/lap phan cung thuc) - khong raise, vi thieu coi khong duoc chan
    viec ghi lai alarm_events."""
    result = get_supabase().table("devices").select("id, mqtt_topic").eq("type", "alarm_unit").execute()
    if not result.data:
        return None
    if len(result.data) > 1:
        raise RuntimeError("Co nhieu devices type='alarm_unit' - can chi dinh device_id cu the")
    return result.data[0]


def _time_in_forbidden_window(now_t: time, start_t: time, end_t: time) -> bool:
    """Khung gio cam co the vat qua nua dem (vd 20:00-07:00) - xu ly rieng truong hop nay."""
    if start_t <= end_t:
        return start_t <= now_t <= end_t
    return now_t >= start_t or now_t <= end_t


def is_zone_currently_armed(zone: dict, when: datetime) -> bool:
    if not zone.get("is_armed"):
        return False
    schedule = zone.get("active_schedule") or {}
    start_t = time.fromisoformat(schedule.get("start", "20:00"))
    end_t = time.fromisoformat(schedule.get("end", "07:00"))
    return _time_in_forbidden_window(when.time(), start_t, end_t)


def _recent_event_within_cooldown(zone_id: str, when: datetime) -> bool:
    cutoff = (when - timedelta(seconds=COOLDOWN_SECONDS)).isoformat()
    recent = (
        get_supabase()
        .table("alarm_events")
        .select("id")
        .eq("zone_id", zone_id)
        .gte("detected_at", cutoff)
        .limit(1)
        .execute()
    )
    return bool(recent.data)


def save_snapshot(camera_id: str, image_base64: str) -> str:
    """Luu anh snapshot ra dia local (storage/alarm_snapshots/) - CHUA co Supabase Storage
    bucket cau hinh trong .env/config.py hien tai, nen tam luu local, ghi duong dan vao
    snapshots.storage_path. Tra ve duong dan file da luu."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    file_name = f"{camera_id}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}.jpg"
    file_path = SNAPSHOT_DIR / file_name
    file_path.write_bytes(b64decode(image_base64))
    return str(file_path)


def evaluate_detection(
    *,
    camera_id: str,
    confidence: float,
    bounding_box: Optional[dict] = None,
    snapshot_path: Optional[str] = None,
) -> dict:
    """Nhan 1 detection DA duoc script giam sat xac nhan (>=3 frame lien tiep). Tra ve
    {"status": "intrusion"|"ignored_not_armed"|"ignored_cooldown", "event": dict|None}."""
    zone = get_default_zone()
    now = datetime.now(timezone.utc)

    if not is_zone_currently_armed(zone, now):
        return {"status": "ignored_not_armed", "event": None}

    if _recent_event_within_cooldown(zone["id"], now):
        return {"status": "ignored_cooldown", "event": None}

    snapshot_url = None
    if snapshot_path:
        snap = get_supabase().table("snapshots").insert({
            "camera_id": camera_id,
            "trigger_type": "alarm",
            "storage_path": snapshot_path,
        }).execute()
        if snap.data:
            snapshot_url = snap.data[0]["storage_path"]

    event = get_supabase().table("alarm_events").insert({
        "camera_id": camera_id,
        "zone_id": zone["id"],
        "event_type": "intrusion",  # CHECK constraint da test thuc: chi 'intrusion' hop le, 'person_detected'/'motion'/... deu bi tu choi
        "confidence": confidence,
        "bounding_box": bounding_box,
        "snapshot_url": snapshot_url,
    }).execute()
    event_row = event.data[0]

    _trigger_buzzer()
    _notify_admins(event_row["id"])

    return {"status": "intrusion", "event": event_row}


def _trigger_buzzer() -> None:
    device = get_alarm_device()
    if device is None:
        logger.info("Chua co devices type='alarm_unit' nao cau hinh - bo qua buoc bat coi")
        return
    alarm_mqtt.publish_cmd(device["mqtt_topic"], {
        "action": "trigger_buzzer",
        "duration_sec": BUZZER_DURATION_SECONDS,
    })


def _notify_admins(event_id: str) -> None:
    # profiles.role chua xac nhan duoc day du gia tri enum hop le (CHUA co RPC SQL de tra
    # pg_get_constraintdef nhu Access Control da lam) - nen tam thong bao cho MOI profile
    # dang active, khong loc theo role de tranh doan sai gia tri.
    admins = get_supabase().table("profiles").select("id").eq("is_active", True).execute()
    if not admins.data:
        return
    rows = [{"event_id": event_id, "profile_id": p["id"], "channel": "dashboard"} for p in admins.data]
    get_supabase().table("alarm_notifications").insert(rows).execute()
