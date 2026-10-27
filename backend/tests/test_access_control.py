"""
Test luong quyet dinh 3 trang thai accepted/rejected/unknown cua access_control.py -
day la phan logic quan trong nhat cua module Access Control (yeu cau tu dinh huong GVHD,
thay the True/False don gian). Dung FakeSupabase (xem conftest.py), khong can Supabase that.
"""
import datetime as dt_module

import pytest

from app.services import access_control

EMPLOYEE_ID = "emp-1"
ACCESS_POINT_ID = "ap-1"

# Thu Ba (Tuesday), 10:00 - trong khung gio hanh chinh mac dinh 07:00-19:00, T2-T6.
_TUESDAY_10AM = dt_module.datetime(2026, 10, 27, 10, 0, 0)
# Chu Nhat (Sunday), 10:00 - ngoai allowed_days mac dinh.
_SUNDAY_10AM = dt_module.datetime(2026, 11, 1, 10, 0, 0)
# Thu Ba, 22:00 - dung ngay nhung ngoai khung gio.
_TUESDAY_10PM = dt_module.datetime(2026, 10, 27, 22, 0, 0)


class _FixedDateTime(dt_module.datetime):
    _fixed_now = _TUESDAY_10AM

    @classmethod
    def now(cls, tz=None):
        return cls._fixed_now


def _freeze_time(monkeypatch, when: dt_module.datetime):
    _FixedDateTime._fixed_now = when
    monkeypatch.setattr(access_control, "datetime", _FixedDateTime)


def _patch_supabase(monkeypatch, fake_supabase):
    monkeypatch.setattr(access_control, "get_supabase", lambda: fake_supabase)


def _default_policy():
    return {
        "employee_id": EMPLOYEE_ID,
        "access_point_id": ACCESS_POINT_ID,
        "allowed_days": ["mon", "tue", "wed", "thu", "fri"],
        "allowed_time_start": "07:00:00",
        "allowed_time_end": "19:00:00",
        "is_active": True,
    }


def test_unknown_when_not_matched(monkeypatch, fake_supabase):
    _patch_supabase(monkeypatch, fake_supabase)
    _freeze_time(monkeypatch, _TUESDAY_10AM)

    decision = access_control.evaluate_and_log(
        employee_id=EMPLOYEE_ID, access_point_id=ACCESS_POINT_ID, method="face", matched=False
    )

    assert decision == {"result": "unknown"}


def test_unknown_when_employee_id_missing_even_if_matched(monkeypatch, fake_supabase):
    _patch_supabase(monkeypatch, fake_supabase)
    _freeze_time(monkeypatch, _TUESDAY_10AM)

    decision = access_control.evaluate_and_log(
        employee_id=None, access_point_id=ACCESS_POINT_ID, method="fingerprint", matched=True
    )

    assert decision == {"result": "unknown"}


def test_rejected_when_employee_inactive(monkeypatch, fake_supabase):
    fake_supabase.store["employees"] = [{"id": EMPLOYEE_ID, "status": "inactive"}]
    fake_supabase.store["access_policies"] = [_default_policy()]
    _patch_supabase(monkeypatch, fake_supabase)
    _freeze_time(monkeypatch, _TUESDAY_10AM)

    decision = access_control.evaluate_and_log(
        employee_id=EMPLOYEE_ID, access_point_id=ACCESS_POINT_ID, method="face", matched=True
    )

    assert decision == {"result": "rejected"}


def test_rejected_when_no_policy_at_all(monkeypatch, fake_supabase):
    fake_supabase.store["employees"] = [{"id": EMPLOYEE_ID, "status": "active"}]
    _patch_supabase(monkeypatch, fake_supabase)
    _freeze_time(monkeypatch, _TUESDAY_10AM)

    decision = access_control.evaluate_and_log(
        employee_id=EMPLOYEE_ID, access_point_id=ACCESS_POINT_ID, method="face", matched=True
    )

    assert decision == {"result": "rejected"}


def test_rejected_when_outside_allowed_weekday(monkeypatch, fake_supabase):
    fake_supabase.store["employees"] = [{"id": EMPLOYEE_ID, "status": "active"}]
    fake_supabase.store["access_policies"] = [_default_policy()]
    _patch_supabase(monkeypatch, fake_supabase)
    _freeze_time(monkeypatch, _SUNDAY_10AM)

    decision = access_control.evaluate_and_log(
        employee_id=EMPLOYEE_ID, access_point_id=ACCESS_POINT_ID, method="fingerprint", matched=True
    )

    assert decision == {"result": "rejected"}


def test_rejected_when_outside_allowed_time_window(monkeypatch, fake_supabase):
    fake_supabase.store["employees"] = [{"id": EMPLOYEE_ID, "status": "active"}]
    fake_supabase.store["access_policies"] = [_default_policy()]
    _patch_supabase(monkeypatch, fake_supabase)
    _freeze_time(monkeypatch, _TUESDAY_10PM)

    decision = access_control.evaluate_and_log(
        employee_id=EMPLOYEE_ID, access_point_id=ACCESS_POINT_ID, method="face", matched=True
    )

    assert decision == {"result": "rejected"}


def test_accepted_when_identity_matched_and_policy_allows(monkeypatch, fake_supabase):
    fake_supabase.store["employees"] = [{"id": EMPLOYEE_ID, "status": "active"}]
    fake_supabase.store["access_policies"] = [_default_policy()]
    _patch_supabase(monkeypatch, fake_supabase)
    _freeze_time(monkeypatch, _TUESDAY_10AM)

    decision = access_control.evaluate_and_log(
        employee_id=EMPLOYEE_ID, access_point_id=ACCESS_POINT_ID, method="face", matched=True, confidence=0.97
    )

    assert decision == {"result": "accepted"}


@pytest.mark.parametrize(
    "app_result,db_result",
    [("accepted", "granted"), ("rejected", "denied"), ("unknown", "unknown")],
)
def test_access_logs_row_uses_db_vocabulary_not_app_vocabulary(monkeypatch, fake_supabase, app_result, db_result):
    """access_logs.result trong Supabase bi CHECK constraint chi nhan granted/denied/unknown
    (khac voi tu vung accepted/rejected/unknown dung trong app) - xem RESULT_TO_DB trong
    access_control.py. Test nay dam bao dong ghi vao DB luon dung tu vung DB, du quyet dinh
    cua app la gi."""
    if app_result == "accepted":
        fake_supabase.store["employees"] = [{"id": EMPLOYEE_ID, "status": "active"}]
        fake_supabase.store["access_policies"] = [_default_policy()]
        matched = True
        when = _TUESDAY_10AM
    elif app_result == "rejected":
        fake_supabase.store["employees"] = [{"id": EMPLOYEE_ID, "status": "active"}]
        matched = True
        when = _TUESDAY_10AM
    else:
        matched = False
        when = _TUESDAY_10AM

    _patch_supabase(monkeypatch, fake_supabase)
    _freeze_time(monkeypatch, when)

    decision = access_control.evaluate_and_log(
        employee_id=EMPLOYEE_ID, access_point_id=ACCESS_POINT_ID, method="face", matched=matched
    )
    assert decision["result"] == app_result

    inserted = fake_supabase.store["access_logs"][-1]
    assert inserted["result"] == db_result


def test_parse_time_accepts_hh_mm_and_hh_mm_ss():
    assert access_control.parse_time("07:00") == dt_module.time(7, 0, 0)
    assert access_control.parse_time("19:30:15") == dt_module.time(19, 30, 15)
