"""
FakeSupabase gia lap du dung .table(name).select()/eq()/insert()/execute() de test logic
nghiep vu (access_control, access_policies) ma KHONG can ket noi Supabase that - doc lap
voi mang/credential, chay duoc o may nao cung nhu nhau.

Chi ho tro dung cac pattern goi thuc su dang dung trong code (select+eq nhieu lan roi
execute, hoac insert roi execute) - khong phai ban sao day du PostgREST.
"""
from types import SimpleNamespace

import pytest


class FakeTable:
    def __init__(self, store: dict, name: str):
        self._store = store
        self._name = name
        self._filters: dict = {}
        self._mode: str | None = None
        self._insert_data: dict | None = None

    def select(self, *_args, **_kwargs):
        self._mode = "select"
        return self

    def eq(self, col: str, val):
        self._filters[col] = val
        return self

    def insert(self, data: dict):
        self._mode = "insert"
        self._insert_data = data
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self._mode == "insert":
            row = dict(self._insert_data)
            rows = self._store.setdefault(self._name, [])
            row.setdefault("id", f"fake-{self._name}-{len(rows) + 1}")
            rows.append(row)
            return SimpleNamespace(data=[row])

        rows = self._store.get(self._name, [])
        filtered = [r for r in rows if all(r.get(k) == v for k, v in self._filters.items())]
        return SimpleNamespace(data=filtered)


class FakeSupabase:
    def __init__(self, seed: dict[str, list[dict]] | None = None):
        self.store: dict[str, list[dict]] = {k: list(v) for k, v in (seed or {}).items()}

    def table(self, name: str) -> FakeTable:
        return FakeTable(self.store, name)


@pytest.fixture
def fake_supabase():
    return FakeSupabase()
