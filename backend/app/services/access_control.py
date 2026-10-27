"""
Enforcement access_policies + ghi access_logs — thay luong quyet dinh True/False
don gian bang 3 trang thai, dung yeu cau dinh huong GVHD:

- "unknown":  sinh trac hoc KHONG khop voi ai (nguoi la, hoac sai van tay/khuon mat)
              -> khong xac dinh duoc danh tinh nen khong the cham chinh sach.
- "rejected": danh tinh xac dinh DUNG nhung KHONG duoc phep mo cua ngay luc nay
              (ngoai allowed_days/allowed_time_start-end, chua co access_policies active
              cho (employee, access_point) nay, hoac nhan vien status != 'active').
- "accepted": danh tinh dung VA dang trong khung gio/ngay access_policies cho phep.

Quy uoc allowed_days trong Supabase: mang text 3 ky tu thuong tieng Anh,
vi du ['mon','tue','wed','thu','fri'].

Fail-secure: chi khi ket qua la "accepted" backend moi gui lenh mo cua (open_door) xuong
ESP32 qua MQTT — moi truong hop khac (ke ca loi) cua van giu nguyen trang thai khoa.
"""
from datetime import datetime, time
from typing import Optional

from app.core.supabase_client import get_supabase

WEEKDAY_CODES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_WEEKDAY_CODES = WEEKDAY_CODES  # ten cu, giu lai de khong phai sua cac cho da dung ben duoi

# access_logs.result trong Supabase bi CHECK constraint rang buoc chi nhan
# 'granted'/'denied'/'unknown' (kiem tra qua pg_get_constraintdef, khong phai doan) - nhung
# toan bo app/dashboard/API dung tu vung "accepted/rejected/unknown" theo dung yeu cau doi
# luong quyet dinh ban dau. Dich 2 chieu o day, duy nhat 1 noi, de khong phai doi tu vung
# o moi noi khac (frontend, memory, tai lieu) da xay dung theo accepted/rejected/unknown.
RESULT_TO_DB = {"accepted": "granted", "rejected": "denied", "unknown": "unknown"}
DB_TO_RESULT = {v: k for k, v in RESULT_TO_DB.items()}


def get_primary_access_point() -> dict:
    """He thong hien chi co 1 cua/1 access_point active - lay dung ban ghi do.
    Raise ngay neu cau hinh sai (0 hoac >1 active) de phat hien som, khong am tham
    mac dinh sang mot cua khac.

    access_points.device_id la FK uuid -> devices.id (dung schema goc, KHONG phai chuoi
    "esp32_test_01" nhu topic MQTT) - phai embed sang bang devices de lay devices.mqtt_topic,
    noi luu dung doan device_id dung trong topic MQTT access/{device_id}/...
    Tra ve van la {"id":..., "device_id":...} nhu truoc, chi khac la "device_id" o day da
    duoc resolve thanh chuoi MQTT that - cac noi goi ham nay khong can sua gi them."""
    result = (
        get_supabase()
        .table("access_points")
        .select("id, devices(mqtt_topic)")
        .eq("is_active", True)
        .execute()
    )
    if not result.data:
        raise RuntimeError("Chua co access_point nao active trong Supabase (bang access_points)")
    if len(result.data) > 1:
        raise RuntimeError("Co nhieu access_point active - can chi dinh access_point_id cu the, khong the tu chon")

    row = result.data[0]
    mqtt_device_id = (row.get("devices") or {}).get("mqtt_topic")
    if not mqtt_device_id:
        raise RuntimeError("access_point chua gan devices.mqtt_topic (device_id dung cho MQTT)")
    return {"id": row["id"], "device_id": mqtt_device_id}


def parse_time(value: str) -> time:
    h, m, *rest = value.split(":")
    s = int(rest[0]) if rest else 0
    return time(int(h), int(m), s)


_parse_time = parse_time  # ten cu, giu lai de khong phai sua cac cho da dung ben duoi


def _policy_allows_now(employee_id: str, access_point_id: str, when: datetime) -> bool:
    policies = (
        get_supabase()
        .table("access_policies")
        .select("allowed_days, allowed_time_start, allowed_time_end")
        .eq("employee_id", employee_id)
        .eq("access_point_id", access_point_id)
        .eq("is_active", True)
        .execute()
    )
    if not policies.data:
        return False

    today_code = _WEEKDAY_CODES[when.weekday()]
    now_time = when.time()
    for policy in policies.data:
        if today_code not in (policy.get("allowed_days") or []):
            continue
        start = _parse_time(policy["allowed_time_start"])
        end = _parse_time(policy["allowed_time_end"])
        if start <= now_time <= end:
            return True
    return False


def evaluate_and_log(
    *,
    employee_id: Optional[str],
    access_point_id: str,
    method: str,
    matched: bool,
    confidence: Optional[float] = None,
    snapshot_url: Optional[str] = None,
) -> dict:
    """Chay enforcement + ghi 1 dong access_logs. Tra ve {"result": "accepted"|"rejected"|"unknown"}."""
    if not matched or employee_id is None:
        result = "unknown"
    else:
        emp = get_supabase().table("employees").select("status").eq("id", employee_id).execute()
        employee_active = bool(emp.data) and emp.data[0]["status"] == "active"
        if not employee_active:
            result = "rejected"
        elif _policy_allows_now(employee_id, access_point_id, datetime.now()):
            result = "accepted"
        else:
            result = "rejected"

    get_supabase().table("access_logs").insert({
        "employee_id": employee_id,
        "access_point_id": access_point_id,
        "method": method,
        "result": RESULT_TO_DB[result],
        "confidence": confidence,
        "snapshot_url": snapshot_url,
    }).execute()

    return {"result": result}
