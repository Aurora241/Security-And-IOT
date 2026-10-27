from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.supabase_client import get_supabase
from app.models.employee import EmployeeCreate, EmployeeResponse

router = APIRouter(prefix="/employees", tags=["employees"])


@router.post("", response_model=EmployeeResponse, status_code=201)
def create_employee(payload: EmployeeCreate):
    data = payload.model_dump(mode="json", exclude_none=True)
    result = get_supabase().table("employees").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Không tạo được nhân viên")
    return result.data[0]


@router.get("", response_model=list[EmployeeResponse])
def list_employees():
    result = get_supabase().table("employees").select("*").order("created_at", desc=True).execute()
    return result.data


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: UUID):
    result = get_supabase().table("employees").select("*").eq("id", str(employee_id)).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhân viên")
    return result.data[0]
