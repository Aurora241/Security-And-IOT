"""
Ghi audit_logs cho hanh dong admin (enroll, revoke credential...) - BANG RIENG, tach biet
voi access_logs (log luot ra/vao cua access_control.py), dung theo quyet dinh thiet ke #3.

actor_id luon de None: he thong CHUA co auth/dang nhap thuc su (Quyet dinh thiet ke #2 - auth
middleware se bo sung giai doan sau), nen khong co can cu de gan dung "ai" la nguoi thuc hien -
de trong con hon gia dinh sai.
"""
from typing import Any, Optional

from app.core.supabase_client import get_supabase


def log_action(action: str, target_type: str, target_id: Optional[str] = None, detail: Optional[dict[str, Any]] = None) -> None:
    get_supabase().table("audit_logs").insert({
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "detail": detail,
    }).execute()
