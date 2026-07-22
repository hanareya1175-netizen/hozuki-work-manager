from __future__ import annotations

import csv
import json
import os
import threading
from pathlib import Path
from typing import Any

DATA_DIR = Path("data")
_LOCK = threading.RLock()

_DEFAULT_FIELDS = {
    "members": ["member_id", "name", "email", "password", "role", "status"],
    "recruit": ["id", "date", "type", "place", "detail", "start", "end", "status", "member_id", "member", "notification_status", "notification_batch_id"],
    "results": ["result_id", "recruit_id", "member_id", "member_name", "work_date", "work_type", "result_value", "unit", "take_home_qty", "note", "previous_recruit_status"],
    "places": ["id", "name", "status", "sort_order"],
    "worktypes": ["id", "name", "status", "sort_order"],
    "notifications": ["notification_id", "kind", "member_id", "member_name", "message", "created_at", "read_at", "batch_id"],
    "notification_batches": ["batch_id", "recruit_count", "created_at", "status"],
    "recruit_views": ["member_id", "member_name", "recruit_id", "batch_id", "seen_at"],
}


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if value:
        return value
    try:
        import streamlit as st
        return str(st.secrets.get("DATABASE_URL", "")).strip()
    except Exception:
        return ""


def using_postgres() -> bool:
    return bool(_database_url())


def _connect():
    import psycopg
    return psycopg.connect(_database_url(), autocommit=False)


def initialize() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not using_postgres():
        return
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS hozuki_records (
                collection TEXT NOT NULL,
                record_key TEXT NOT NULL,
                position INTEGER NOT NULL,
                data JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (collection, record_key)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_hozuki_records_collection_position ON hozuki_records(collection, position)")
        conn.commit()


def _path(name: str) -> Path:
    return DATA_DIR / f"{name}.csv"


def _record_key(name: str, row: dict[str, Any], position: int) -> str:
    for key in ("id", "member_id", "result_id", "notification_id", "batch_id"):
        value = str(row.get(key, "")).strip()
        if value:
            return f"{key}:{value}"
    return f"position:{position}"


def read(name: str) -> list[dict[str, str]]:
    initialize()
    if using_postgres():
        with _connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT data FROM hozuki_records WHERE collection=%s ORDER BY position", (name,))
            return [{str(k): "" if v is None else str(v) for k, v in row[0].items()} for row in cur.fetchall()]
    path = _path(name)
    if not path.exists():
        return []
    with _LOCK, path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_all(name: str, rows: list[dict[str, Any]]) -> None:
    initialize()
    clean_rows = [{str(k): "" if v is None else str(v) for k, v in row.items()} for row in rows]
    if using_postgres():
        with _connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM hozuki_records WHERE collection=%s", (name,))
            for pos, row in enumerate(clean_rows, start=1):
                cur.execute(
                    "INSERT INTO hozuki_records(collection,record_key,position,data) VALUES(%s,%s,%s,%s::jsonb)",
                    (name, _record_key(name, row, pos), pos, json.dumps(row, ensure_ascii=False)),
                )
            conn.commit()
        return
    path = _path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(_DEFAULT_FIELDS.get(name, []))
    for row in clean_rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not fields:
        fields = ["id"]
    temp = path.with_suffix(".tmp")
    with _LOCK, temp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(clean_rows)
    temp.replace(path)


def append(name: str, row: dict[str, Any]) -> None:
    rows = read(name); rows.append(row); write_all(name, rows)


def next_id(name: str, field: str) -> str:
    values=[]
    for row in read(name):
        try: values.append(int(str(row.get(field, "0"))))
        except ValueError: pass
    return str(max(values, default=0)+1)


def storage_label() -> str:
    return "クラウドデータベース" if using_postgres() else "ローカルCSV"
