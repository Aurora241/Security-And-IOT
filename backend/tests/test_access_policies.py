"""Test validate_days/validate_time_range trong access_policies.py - logic thuan tuy,
khong dung Supabase, nen khong can fake/mock gi."""
import pytest
from fastapi import HTTPException

from app.api.v1 import access_policies as ap


def test_validate_days_accepts_valid_codes():
    ap._validate_days(["mon", "wed", "fri"])  # khong raise la pass


def test_validate_days_rejects_unknown_code():
    with pytest.raises(HTTPException) as exc_info:
        ap._validate_days(["mon", "weekend"])
    assert exc_info.value.status_code == 400


def test_validate_time_range_accepts_valid_range():
    ap._validate_time_range("07:00", "19:00")  # khong raise la pass


def test_validate_time_range_rejects_start_after_end():
    with pytest.raises(HTTPException) as exc_info:
        ap._validate_time_range("19:00", "07:00")
    assert exc_info.value.status_code == 400


def test_validate_time_range_rejects_equal_start_end():
    with pytest.raises(HTTPException) as exc_info:
        ap._validate_time_range("08:00", "08:00")
    assert exc_info.value.status_code == 400


def test_validate_time_range_rejects_bad_format():
    with pytest.raises(HTTPException) as exc_info:
        ap._validate_time_range("not-a-time", "19:00")
    assert exc_info.value.status_code == 400
