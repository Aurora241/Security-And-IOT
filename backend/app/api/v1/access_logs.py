from fastapi import APIRouter

from app.core.supabase_client import get_supabase
from app.services.access_control import DB_TO_RESULT

router = APIRouter(prefix="/access-logs", tags=["access_logs"])


@router.get("")
def list_access_logs(limit: int = 50):
    # employees(code, full_name): PostgREST tu dong embed theo FK access_logs.employee_id ->
    # employees.id da khai bao trong schema, khong can viet join thu cong.
    result = (
        get_supabase()
        .table("access_logs")
        .select("id, method, result, confidence, timestamp, employees(code, full_name)")
        .order("timestamp", desc=True)
        .limit(limit)
        .execute()
    )
    rows = result.data
    # DB luu 'granted'/'denied'/'unknown' (CHECK constraint) - dich lai thanh
    # 'accepted'/'rejected'/'unknown' cho khop tu vung dashboard/API (xem access_control.py).
    for row in rows:
        row["result"] = DB_TO_RESULT.get(row["result"], row["result"])
    return rows
