from pydantic import BaseModel

from fastapi import APIRouter, HTTPException

from app.core.supabase_client import get_supabase
from app.services import access_control, mqtt_subscriber

router = APIRouter(prefix="/devices/{device_id}", tags=["devices"])


class EnrollFingerprintCommand(BaseModel):
    employee_code: str
    slot_id: int


class VerifyFingerprintCommand(BaseModel):
    employee_code: str
    employee_id: str


@router.post("/enroll-fingerprint", status_code=202)
def trigger_enroll_fingerprint(device_id: str, payload: EnrollFingerprintCommand):
    # Gui lenh xuong ESP32 qua MQTT (topic access/{device_id}/cmd) - thiet bi tu chay
    # buoc quet van tay, khong can go lenh tren Serial Monitor. Ket qua tra ve qua
    # access/{device_id}/enroll_ack (mqtt_subscriber.py da xu ly va luu Supabase).
    mqtt_subscriber.reset_progress(device_id)
    mqtt_subscriber.publish_cmd(device_id, {
        "action": "enroll_fingerprint",
        "employee_code": payload.employee_code,
        "slot_id": payload.slot_id,
    })
    return {"status": "sent", "message": "Da gui lenh xuong thiet bi, dat ngon tay len cam bien."}


@router.get("/enroll-progress")
def get_enroll_progress(device_id: str):
    # Web poll endpoint nay de hien thi tien trinh giong nhu dang xem Serial Monitor
    # (dat ngon tay lan 1, nhac ra, dat lan 2, dang luu...).
    return mqtt_subscriber.get_progress(device_id)


@router.post("/verify-fingerprint", status_code=202)
def trigger_verify_fingerprint(device_id: str, payload: VerifyFingerprintCommand):
    # Verify 1:1: lay dung slot_id da luu cho employee nay, ESP32 chi bao "khop" neu
    # ID cam bien tim thay == slot_id nay - khong phai so voi ca CSDL (1:N).
    existing = (
        get_supabase()
        .table("access_credentials")
        .select("credential_data")
        .eq("employee_id", payload.employee_id)
        .eq("type", "fingerprint")
        .eq("is_active", True)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Nhân viên chưa đăng ký vân tay")

    slot_id = existing.data[0]["credential_data"].get("fingerprint_slot_id")
    if slot_id is None:
        raise HTTPException(status_code=422, detail="Dữ liệu credential vân tay bị thiếu slot_id")

    access_point = access_control.get_primary_access_point()
    if access_point["device_id"] != device_id:
        raise HTTPException(status_code=400, detail="device_id khong khop access_point dang cau hinh")

    mqtt_subscriber.reset_progress(device_id)
    mqtt_subscriber.reset_verify_result(device_id)
    mqtt_subscriber.set_pending_verify(device_id, employee_id=payload.employee_id, access_point_id=access_point["id"])
    mqtt_subscriber.publish_cmd(device_id, {
        "action": "verify_fingerprint",
        "employee_code": payload.employee_code,
        "slot_id": slot_id,
    })
    return {"status": "sent", "message": "Da gui lenh xac thuc xuong thiet bi, dat ngon tay len cam bien."}


@router.get("/verify-result")
def get_verify_result(device_id: str):
    return mqtt_subscriber.get_verify_result(device_id)


@router.get("/slot/{slot_id}")
def resolve_slot_owner(device_id: str, slot_id: int):
    # ESP32 goi endpoint nay khi phat hien van tay trung (fingerFastSearch() ra ID da co
    # chu), de bao ten/ma nhan vien dang so huu slot do thay vi chi bao mot con so tho.
    result = (
        get_supabase()
        .table("access_credentials")
        .select("employee_id, credential_data")
        .eq("type", "fingerprint")
        .eq("is_active", True)
        .execute()
    )
    match = next(
        (row for row in result.data
         if row["credential_data"].get("device_id") == device_id
         and row["credential_data"].get("fingerprint_slot_id") == slot_id),
        None,
    )
    if not match:
        raise HTTPException(status_code=404, detail="Khong tim thay nhan vien so huu slot nay")

    emp = get_supabase().table("employees").select("code, full_name").eq("id", match["employee_id"]).execute()
    if not emp.data:
        raise HTTPException(status_code=404, detail="Nhan vien khong con ton tai")

    return {"employee_code": emp.data[0]["code"], "full_name": emp.data[0]["full_name"]}


@router.get("/next-slot")
def suggest_next_slot(device_id: str):
    # Goi y slot_id ke tiep con trong: lay max(fingerprint_slot_id) da dung cua device nay + 1.
    result = (
        get_supabase()
        .table("access_credentials")
        .select("credential_data")
        .eq("type", "fingerprint")
        .execute()
    )
    used_slots = [
        row["credential_data"].get("fingerprint_slot_id")
        for row in result.data
        if row.get("credential_data", {}).get("device_id") == device_id
        and row["credential_data"].get("fingerprint_slot_id") is not None
    ]
    next_slot = (max(used_slots) + 1) if used_slots else 1
    return {"slot_id": next_slot}
