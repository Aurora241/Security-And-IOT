import base64
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.supabase_client import get_supabase
from app.models.access_credential import AccessCredentialCreate, AccessCredentialResponse, FaceEnrollRequest
from app.services import access_control, audit_log
from app.services.face_embedding import FACENET512_THRESHOLD, FaceEmbeddingError, cosine_distance, extract_embedding

# Import tri hoan (khong o dau file) de tranh circular import: mqtt_subscriber.py lai import
# tu module nay (DuplicateCredentialError, enroll_credential_core) o muc top-level cua no.

router = APIRouter(prefix="/employees/{employee_id}/credentials", tags=["access_credentials"])


class DuplicateCredentialError(Exception):
    pass


def enroll_credential_core(employee_id: UUID, cred_type: str, credential_data: dict) -> dict:
    """Logic dùng chung cho endpoint HTTP và MQTT subscriber (ESP32 enroll qua broker)."""
    supabase = get_supabase()

    # Partial unique index (employee_id, type) WHERE is_active=true chặn insert trùng —
    # bắt lỗi và trả thông báo rõ ràng thay vì để lộ lỗi DB thô.
    existing = (
        supabase.table("access_credentials")
        .select("id")
        .eq("employee_id", str(employee_id))
        .eq("type", cred_type)
        .eq("is_active", True)
        .execute()
    )
    if existing.data:
        raise DuplicateCredentialError(
            f"Nhân viên đã có credential '{cred_type}' đang active — thu hồi (revoke) trước khi đăng ký lại"
        )

    data = {"employee_id": str(employee_id), "type": cred_type, "credential_data": credential_data}
    result = supabase.table("access_credentials").insert(data).execute()
    if not result.data:
        raise RuntimeError("Không tạo được credential")

    credential = result.data[0]
    audit_log.log_action(
        action="enroll_credential",
        target_type="access_credential",
        target_id=credential["id"],
        detail={"employee_id": str(employee_id), "type": cred_type},
    )
    return credential


@router.post("", response_model=AccessCredentialResponse, status_code=201)
def enroll_credential(employee_id: UUID, payload: AccessCredentialCreate):
    # Quyết định thiết kế #2: chỉ Admin được enroll — auth middleware sẽ bổ sung ở giai đoạn sau.
    if str(employee_id) != str(payload.employee_id):
        raise HTTPException(status_code=400, detail="employee_id trên URL và trong body không khớp")

    try:
        return enroll_credential_core(employee_id, payload.type, payload.credential_data)
    except DuplicateCredentialError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/face", response_model=AccessCredentialResponse, status_code=201)
def enroll_face_credential(employee_id: UUID, payload: FaceEnrollRequest):
    if str(employee_id) != str(payload.employee_id):
        raise HTTPException(status_code=400, detail="employee_id trên URL và trong body không khớp")

    image_data = payload.image_base64
    if "," in image_data:
        image_data = image_data.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(image_data)
    except Exception:
        raise HTTPException(status_code=400, detail="image_base64 không hợp lệ")

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        embedding = extract_embedding(tmp_path)
    except FaceEmbeddingError as e:
        raise HTTPException(status_code=422, detail=f"Không nhận diện được khuôn mặt: {e}")
    finally:
        # Chính sách đã chốt: không lưu ảnh gốc, chỉ lưu embedding — xoá ảnh tạm ngay sau khi trích xong.
        Path(tmp_path).unlink(missing_ok=True)

    duplicate_owner = _find_duplicate_face_owner(employee_id, embedding)
    if duplicate_owner is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Khuôn mặt này đã được đăng ký cho nhân viên {duplicate_owner}",
        )

    try:
        return enroll_credential_core(employee_id, "face", {"embedding": embedding})
    except DuplicateCredentialError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _find_duplicate_face_owner(employee_id: UUID, new_embedding: list[float]) -> str | None:
    """So embedding moi voi embedding active cua MOI nhan vien KHAC - tra ve ma nhan vien
    da so huu neu trung (distance <= threshold), None neu khong trung ai."""
    others = (
        get_supabase()
        .table("access_credentials")
        .select("employee_id, credential_data")
        .eq("type", "face")
        .eq("is_active", True)
        .neq("employee_id", str(employee_id))
        .execute()
    )
    if not others.data:
        return None

    other_employee_ids = {row["employee_id"] for row in others.data}
    employees = (
        get_supabase()
        .table("employees")
        .select("id, code")
        .in_("id", list(other_employee_ids))
        .execute()
    )
    code_by_id = {row["id"]: row["code"] for row in employees.data}

    for row in others.data:
        distance = cosine_distance(new_embedding, row["credential_data"]["embedding"])
        if distance <= FACENET512_THRESHOLD:
            return code_by_id.get(row["employee_id"], row["employee_id"])
    return None


@router.post("/face/verify")
def verify_face_credential(employee_id: UUID, payload: FaceEnrollRequest):
    # Verify 1:1: so khop anh vua chup voi DUNG embedding da luu cua employee_id nay,
    # khong so voi toan bo CSDL - dung theo quyet dinh thiet ke #1 (verification 1:1).
    if str(employee_id) != str(payload.employee_id):
        raise HTTPException(status_code=400, detail="employee_id trên URL và trong body không khớp")

    existing = (
        get_supabase()
        .table("access_credentials")
        .select("credential_data")
        .eq("employee_id", str(employee_id))
        .eq("type", "face")
        .eq("is_active", True)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Nhân viên chưa đăng ký khuôn mặt")

    stored_embedding = existing.data[0]["credential_data"]["embedding"]

    image_data = payload.image_base64
    if "," in image_data:
        image_data = image_data.split(",", 1)[1]
    try:
        image_bytes = base64.b64decode(image_data)
    except Exception:
        raise HTTPException(status_code=400, detail="image_base64 không hợp lệ")

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        new_embedding = extract_embedding(tmp_path)
    except FaceEmbeddingError as e:
        raise HTTPException(status_code=422, detail=f"Không nhận diện được khuôn mặt: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    distance = cosine_distance(stored_embedding, new_embedding)
    verified = distance <= FACENET512_THRESHOLD
    # "Do tin cay" quy uoc = 1 - distance (cosine distance cang nho cang giong, confidence
    # cang gan 1 la cang chac chan dung nguoi) - chi de ghi access_logs, khong anh huong verified.
    confidence = round(1 - distance, 4)

    access_point = access_control.get_primary_access_point()
    decision = access_control.evaluate_and_log(
        employee_id=str(employee_id),
        access_point_id=access_point["id"],
        method="face",
        matched=verified,
        confidence=confidence,
    )
    if decision["result"] == "accepted":
        from app.services import mqtt_subscriber  # import tri hoan, xem comment dau file

        mqtt_subscriber.publish_cmd(access_point["device_id"], {"action": "open_door"})

    return {
        "verified": verified,
        "distance": distance,
        "threshold": FACENET512_THRESHOLD,
        "result": decision["result"],
    }


@router.get("", response_model=list[AccessCredentialResponse])
def list_credentials(employee_id: UUID):
    result = (
        get_supabase()
        .table("access_credentials")
        .select("*")
        .eq("employee_id", str(employee_id))
        .order("enrolled_at", desc=True)
        .execute()
    )
    return result.data


@router.patch("/{credential_id}/revoke", response_model=AccessCredentialResponse)
def revoke_credential(employee_id: UUID, credential_id: UUID):
    # Soft-delete theo quyết định thiết kế #2 — không xoá cứng, giữ vết cho audit.
    result = (
        get_supabase()
        .table("access_credentials")
        .update({"is_active": False})
        .eq("id", str(credential_id))
        .eq("employee_id", str(employee_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Không tìm thấy credential")

    credential = result.data[0]
    audit_log.log_action(
        action="revoke_credential",
        target_type="access_credential",
        target_id=credential["id"],
        detail={"employee_id": str(employee_id), "type": credential.get("type")},
    )
    return credential
