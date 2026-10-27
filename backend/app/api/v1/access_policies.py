from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.supabase_client import get_supabase
from app.models.access_policy import AccessPolicyCreate, AccessPolicyResponse, AccessPolicyUpdate
from app.services import access_control, audit_log

router = APIRouter(prefix="/employees/{employee_id}/policies", tags=["access_policies"])


def _validate_days(allowed_days: list[str]) -> None:
    invalid = [d for d in allowed_days if d not in access_control.WEEKDAY_CODES]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"allowed_days khong hop le: {invalid} - chi chap nhan {access_control.WEEKDAY_CODES}",
        )


def _validate_time_range(start: str, end: str) -> None:
    try:
        parsed_start, parsed_end = access_control.parse_time(start), access_control.parse_time(end)
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="allowed_time_start/allowed_time_end phai dang HH:MM")
    if parsed_start >= parsed_end:
        raise HTTPException(status_code=400, detail="allowed_time_start phai nho hon allowed_time_end")


@router.get("", response_model=list[AccessPolicyResponse])
def list_policies(employee_id: UUID):
    result = (
        get_supabase()
        .table("access_policies")
        .select("*")
        .eq("employee_id", str(employee_id))
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.post("", response_model=AccessPolicyResponse, status_code=201)
def create_policy(employee_id: UUID, payload: AccessPolicyCreate):
    _validate_days(payload.allowed_days)
    _validate_time_range(payload.allowed_time_start, payload.allowed_time_end)

    access_point = access_control.get_primary_access_point()
    data = {
        "employee_id": str(employee_id),
        "access_point_id": access_point["id"],
        "allowed_days": payload.allowed_days,
        "allowed_time_start": payload.allowed_time_start,
        "allowed_time_end": payload.allowed_time_end,
        "is_active": True,
    }
    result = get_supabase().table("access_policies").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Khong tao duoc chinh sach")

    policy = result.data[0]
    audit_log.log_action(
        action="create_policy",
        target_type="access_policy",
        target_id=policy["id"],
        detail={"employee_id": str(employee_id), **payload.model_dump()},
    )
    return policy


@router.patch("/{policy_id}", response_model=AccessPolicyResponse)
def update_policy(employee_id: UUID, policy_id: UUID, payload: AccessPolicyUpdate):
    update_data = payload.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Khong co truong nao de cap nhat")

    if "allowed_days" in update_data:
        _validate_days(update_data["allowed_days"])

    existing = (
        get_supabase()
        .table("access_policies")
        .select("allowed_time_start, allowed_time_end")
        .eq("id", str(policy_id))
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Khong tim thay chinh sach")

    start = update_data.get("allowed_time_start", existing.data[0]["allowed_time_start"])
    end = update_data.get("allowed_time_end", existing.data[0]["allowed_time_end"])
    if "allowed_time_start" in update_data or "allowed_time_end" in update_data:
        _validate_time_range(start, end)

    result = (
        get_supabase()
        .table("access_policies")
        .update(update_data)
        .eq("id", str(policy_id))
        .eq("employee_id", str(employee_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Khong tim thay chinh sach")

    policy = result.data[0]
    audit_log.log_action(
        action="update_policy",
        target_type="access_policy",
        target_id=policy["id"],
        detail={"employee_id": str(employee_id), **update_data},
    )
    return policy
