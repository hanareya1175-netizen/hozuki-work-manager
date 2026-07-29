from __future__ import annotations

import csv
import json
import os
import threading

import streamlit as st
from pathlib import Path
from typing import Any

DATA_DIR = Path("data")
_LOCK = threading.RLock()
_INIT_LOCK = threading.Lock()
_INITIALIZED = False

_DEFAULT_FIELDS = {
    "members": ["member_id", "name", "email", "password", "role", "status", "phone"],
    "recruit": ["id", "date", "type", "place", "detail", "start", "end", "status", "member_id", "member", "notification_status", "notification_batch_id"],
    "results": ["result_id", "recruit_id", "member_id", "member_name", "work_date", "work_type", "result_value", "unit", "take_home_qty", "note", "previous_recruit_status"],
    "places": ["id", "name", "status", "sort_order"],
    "worktypes": ["id", "name", "status", "sort_order"],
    "notifications": ["notification_id", "kind", "member_id", "member_name", "message", "created_at", "read_at", "batch_id"],
    "notification_batches": ["batch_id", "recruit_count", "created_at", "status"],
    "recruit_views": ["member_id", "member_name", "recruit_id", "batch_id", "seen_at", "last_seen_batch_id"],
}

_MIGRATION_KEY = "initial_csv_import_v2"


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


def _path(name: str) -> Path:
    return DATA_DIR / f"{name}.csv"


def _read_csv(name: str) -> list[dict[str, str]]:
    path = _path(name)
    if not path.exists():
        return []
    with _LOCK, path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _record_key(name: str, row: dict[str, Any], position: int) -> str:
    """Return a collection-appropriate stable key.

    The order matters: notification rows contain both member_id and
    notification_id.  Using member_id there would allow only one notification
    per member, which causes a PostgreSQL primary-key violation.
    """
    key_fields = {
        "members": ("member_id",),
        "recruit": ("id",),
        "results": ("result_id",),
        "places": ("id",),
        "worktypes": ("id",),
        "notifications": ("notification_id",),
        "notification_batches": ("batch_id",),
    }
    for key in key_fields.get(name, ("id", "result_id", "notification_id", "batch_id", "member_id")):
        value = str(row.get(key, "")).strip()
        if value:
            return f"{key}:{value}"

    # recruit_views intentionally has no single unique-ID column and is
    # rewritten as a whole, so its row position is the safest lossless key.
    return f"position:{position}"


def _insert_rows(cur, name: str, rows: list[dict[str, Any]]) -> None:
    for pos, row in enumerate(rows, start=1):
        clean = {str(k): "" if v is None else str(v) for k, v in row.items()}
        cur.execute(
            """
            INSERT INTO hozuki_records(collection, record_key, position, data)
            VALUES(%s, %s, %s, %s::jsonb)
            ON CONFLICT (collection, record_key)
            DO UPDATE SET position=EXCLUDED.position, data=EXCLUDED.data, updated_at=NOW()
            """,
            (name, _record_key(name, clean, pos), pos, json.dumps(clean, ensure_ascii=False)),
        )


def initialize() -> None:
    """保存先を初期化する。同一プロセス内では一度だけ実行する。"""
    global _INITIALIZED
    if _INITIALIZED:
        return

    with _INIT_LOCK:
        if _INITIALIZED:
            return

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not using_postgres():
            _INITIALIZED = True
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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS hozuki_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_hozuki_records_collection_position "
                "ON hozuki_records(collection, position)"
            )

            # 同時起動時にも初回移行が重ならないよう、トランザクション内でロックする。
            cur.execute("SELECT pg_advisory_xact_lock(20260723)")
            cur.execute("SELECT value FROM hozuki_meta WHERE key=%s", (_MIGRATION_KEY,))
            migrated = cur.fetchone() is not None

            if not migrated:
                cur.execute("SELECT COUNT(*) FROM hozuki_records")
                record_count = int(cur.fetchone()[0])

                # 完全に空のDBだけ、GitHub同梱CSVから初期データを取り込む。
                if record_count == 0:
                    for name in _DEFAULT_FIELDS:
                        _insert_rows(cur, name, _read_csv(name))

                cur.execute(
                    """
                    INSERT INTO hozuki_meta(key, value)
                    VALUES(%s, %s)
                    ON CONFLICT (key) DO UPDATE
                    SET value=EXCLUDED.value, updated_at=NOW()
                    """,
                    (_MIGRATION_KEY, "completed"),
                )
            conn.commit()
        _INITIALIZED = True


@st.cache_data(show_spinner=False, ttl=30)
def _read_postgres_cached(name: str) -> list[dict[str, str]]:
    """同じコレクションの反復読込みを短時間キャッシュする。"""
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT data FROM hozuki_records WHERE collection=%s ORDER BY position",
            (name,),
        )
        return [
            {str(k): "" if v is None else str(v) for k, v in row[0].items()}
            for row in cur.fetchall()
        ]


def _clear_read_cache() -> None:
    _read_postgres_cached.clear()


def read(name: str) -> list[dict[str, str]]:
    initialize()
    if using_postgres():
        return _read_postgres_cached(name)
    return _read_csv(name)


def write_all(name: str, rows: list[dict[str, Any]]) -> None:
    initialize()
    clean_rows = [
        {str(k): "" if v is None else str(v) for k, v in row.items()}
        for row in rows
    ]
    if using_postgres():
        with _connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(20260724)")
            cur.execute("DELETE FROM hozuki_records WHERE collection=%s", (name,))
            _insert_rows(cur, name, clean_rows)
            conn.commit()
        _clear_read_cache()
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
        writer.writeheader()
        writer.writerows(clean_rows)
    temp.replace(path)


def append(name: str, row: dict[str, Any]) -> None:
    initialize()
    if using_postgres():
        with _connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(20260725)")
            cur.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 FROM hozuki_records WHERE collection=%s",
                (name,),
            )
            position = int(cur.fetchone()[0])
            clean = {str(k): "" if v is None else str(v) for k, v in row.items()}
            cur.execute(
                """
                INSERT INTO hozuki_records(collection, record_key, position, data)
                VALUES(%s, %s, %s, %s::jsonb)
                ON CONFLICT (collection, record_key)
                DO UPDATE SET position=EXCLUDED.position, data=EXCLUDED.data, updated_at=NOW()
                """,
                (name, _record_key(name, clean, position), position, json.dumps(clean, ensure_ascii=False)),
            )
            conn.commit()
        _clear_read_cache()
        return

    rows = read(name)
    rows.append(row)
    write_all(name, rows)


def append_recruit_view_if_missing(row: dict[str, Any]) -> bool:
    """Append one recruit-view record only when the member/recruit pair is absent.

    PostgreSQL uses a single short transaction instead of reading and rewriting
    the whole recruit_views collection.  This keeps smartphone detail opening
    responsive even when the database is remote.
    """
    initialize()
    clean = {str(k): "" if v is None else str(v) for k, v in row.items()}
    member_id = clean.get("member_id", "").strip()
    member_name = clean.get("member_name", "").strip()
    recruit_id = clean.get("recruit_id", "").strip()
    if not recruit_id or (not member_id and not member_name):
        return False

    if using_postgres():
        with _connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(20260726)")
            cur.execute(
                """
                SELECT 1
                  FROM hozuki_records
                 WHERE collection='recruit_views'
                   AND data->>'recruit_id'=%s
                   AND (
                        (%s <> '' AND data->>'member_id'=%s)
                        OR (%s <> '' AND data->>'member_name'=%s)
                   )
                 LIMIT 1
                """,
                (recruit_id, member_id, member_id, member_name, member_name),
            )
            if cur.fetchone() is not None:
                conn.commit()
                return False
            cur.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 FROM hozuki_records WHERE collection='recruit_views'"
            )
            position = int(cur.fetchone()[0])
            cur.execute(
                """
                INSERT INTO hozuki_records(collection, record_key, position, data)
                VALUES('recruit_views', %s, %s, %s::jsonb)
                """,
                (f"view:{member_id or member_name}:{recruit_id}", position, json.dumps(clean, ensure_ascii=False)),
            )
            conn.commit()
        _clear_read_cache()
        return True

    rows = read("recruit_views")
    exists = any(
        str(r.get("recruit_id", "")).strip() == recruit_id
        and (
            (member_id and str(r.get("member_id", "")).strip() == member_id)
            or (member_name and str(r.get("member_name", "")).strip() == member_name)
        )
        for r in rows
    )
    if exists:
        return False
    rows.append(clean)
    write_all("recruit_views", rows)
    return True


def next_id(name: str, field: str) -> str:
    values: list[int] = []
    for row in read(name):
        try:
            values.append(int(str(row.get(field, "0"))))
        except ValueError:
            pass
    return str(max(values, default=0) + 1)


def commit_notification_batch(
    recruits: list[dict[str, Any]],
    notification_rows: list[dict[str, Any]],
    batch_row: dict[str, Any],
) -> None:
    """通知送信に伴う3種類の更新を1回のトランザクションで保存する。

    PostgreSQLでは、募集の通知済み更新・会員別通知追加・通知履歴追加を
    1接続でまとめる。途中で失敗した場合は全体がロールバックされる。
    CSV利用時は従来どおり各ファイルへ保存する。
    """
    initialize()

    clean_recruits = [
        {str(k): "" if v is None else str(v) for k, v in row.items()}
        for row in recruits
    ]
    clean_notifications = [
        {str(k): "" if v is None else str(v) for k, v in row.items()}
        for row in notification_rows
    ]
    clean_batch = {str(k): "" if v is None else str(v) for k, v in batch_row.items()}

    if using_postgres():
        with _connect() as conn, conn.cursor() as cur:
            # 通知処理同士が重なってIDやpositionが競合しないよう直列化する。
            cur.execute("SELECT pg_advisory_xact_lock(20260726)")

            # 募集一覧は現在の並び順を保ったまま置き換える。
            cur.execute("DELETE FROM hozuki_records WHERE collection=%s", ("recruit",))
            _insert_rows(cur, "recruit", clean_recruits)

            # 通知は既存行を消さず、今回分だけをまとめて追加する。
            cur.execute(
                "SELECT COALESCE(MAX(position), 0) FROM hozuki_records WHERE collection=%s",
                ("notifications",),
            )
            notification_position = int(cur.fetchone()[0])
            for offset, row in enumerate(clean_notifications, start=1):
                position = notification_position + offset
                cur.execute(
                    """
                    INSERT INTO hozuki_records(collection, record_key, position, data)
                    VALUES(%s, %s, %s, %s::jsonb)
                    ON CONFLICT (collection, record_key)
                    DO UPDATE SET position=EXCLUDED.position, data=EXCLUDED.data, updated_at=NOW()
                    """,
                    (
                        "notifications",
                        _record_key("notifications", row, position),
                        position,
                        json.dumps(row, ensure_ascii=False),
                    ),
                )

            # 通知バッチ履歴を1件追加する。
            cur.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 FROM hozuki_records WHERE collection=%s",
                ("notification_batches",),
            )
            batch_position = int(cur.fetchone()[0])
            cur.execute(
                """
                INSERT INTO hozuki_records(collection, record_key, position, data)
                VALUES(%s, %s, %s, %s::jsonb)
                ON CONFLICT (collection, record_key)
                DO UPDATE SET position=EXCLUDED.position, data=EXCLUDED.data, updated_at=NOW()
                """,
                (
                    "notification_batches",
                    _record_key("notification_batches", clean_batch, batch_position),
                    batch_position,
                    json.dumps(clean_batch, ensure_ascii=False),
                ),
            )
            conn.commit()

        _clear_read_cache()
        return

    # ローカルCSV互換経路。
    write_all("recruit", clean_recruits)
    existing_notifications = read("notifications")
    existing_notifications.extend(clean_notifications)
    write_all("notifications", existing_notifications)
    existing_batches = read("notification_batches")
    existing_batches.append(clean_batch)
    write_all("notification_batches", existing_batches)



def send_general_notification_batch(*, open_status: str, active_statuses: set[str], created_at: str) -> dict[str, Any]:
    """一般募集通知を、読込みから保存まで1接続・1トランザクションで処理する。

    戻り値: {"sent": bool, "recruit_count": int, "member_count": int, "message": str}
    """
    initialize()

    if not using_postgres():
        recruits = read("recruit")
        targets = [
            r for r in recruits
            if str(r.get("status", "")) == open_status
            and str(r.get("notification_status", "未通知")) == "未通知"
        ]
        if not targets:
            return {"sent": False, "recruit_count": 0, "member_count": 0, "message": ""}

        members = [r for r in read("members") if str(r.get("status", "")) in active_statuses]
        count = len(targets)
        message = f"新しい作業募集が{count}件あります。"
        batch_id = next_id("notification_batches", "batch_id")
        first_id = int(next_id("notifications", "notification_id"))

        target_ids = {str(r.get("id", "")) for r in targets}
        for row in recruits:
            if str(row.get("id", "")) in target_ids:
                row["notification_status"] = "通知済"
                row["notification_batch_id"] = batch_id

        notification_rows = []
        for offset, member in enumerate(members):
            notification_rows.append({
                "notification_id": str(first_id + offset),
                "kind": "一般募集",
                "member_id": str(member.get("member_id", "")),
                "member_name": str(member.get("name", "")),
                "message": message,
                "created_at": created_at,
                "read_at": "",
                "batch_id": batch_id,
            })

        commit_notification_batch(
            recruits,
            notification_rows,
            {"batch_id": batch_id, "recruit_count": str(count), "created_at": created_at, "status": "送信済"},
        )
        return {"sent": True, "recruit_count": count, "member_count": len(members), "message": message}

    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(20260727)")
        cur.execute(
            """
            SELECT collection, data
            FROM hozuki_records
            WHERE collection IN ('recruit', 'members', 'notifications', 'notification_batches')
            ORDER BY collection, position
            """
        )
        grouped: dict[str, list[dict[str, str]]] = {
            "recruit": [], "members": [], "notifications": [], "notification_batches": []
        }
        for collection, data in cur.fetchall():
            grouped[str(collection)].append({str(k): "" if v is None else str(v) for k, v in data.items()})

        recruits = grouped["recruit"]
        targets = [
            r for r in recruits
            if str(r.get("status", "")) == open_status
            and str(r.get("notification_status", "未通知")) == "未通知"
        ]
        if not targets:
            conn.rollback()
            return {"sent": False, "recruit_count": 0, "member_count": 0, "message": ""}

        members = [r for r in grouped["members"] if str(r.get("status", "")) in active_statuses]

        def _max_numeric(rows: list[dict[str, str]], field: str) -> int:
            values = []
            for row in rows:
                try:
                    values.append(int(str(row.get(field, "0"))))
                except (TypeError, ValueError):
                    pass
            return max(values, default=0)

        count = len(targets)
        message = f"新しい作業募集が{count}件あります。"
        batch_id = str(_max_numeric(grouped["notification_batches"], "batch_id") + 1)
        first_notification_id = _max_numeric(grouped["notifications"], "notification_id") + 1

        target_ids = {str(row.get("id", "")) for row in targets}
        changed_recruits = []
        for position, row in enumerate(recruits, start=1):
            if str(row.get("id", "")) in target_ids:
                row["notification_status"] = "通知済"
                row["notification_batch_id"] = batch_id
                changed_recruits.append({
                    "record_key": _record_key("recruit", row, position),
                    "position": position,
                    "data": row,
                })

        if changed_recruits:
            cur.execute(
                """
                INSERT INTO hozuki_records(collection, record_key, position, data)
                SELECT 'recruit', x.record_key, x.position, x.data
                FROM jsonb_to_recordset(%s::jsonb) AS x(record_key text, position integer, data jsonb)
                ON CONFLICT (collection, record_key)
                DO UPDATE SET position=EXCLUDED.position, data=EXCLUDED.data, updated_at=NOW()
                """,
                (json.dumps(changed_recruits, ensure_ascii=False),),
            )

        cur.execute(
            "SELECT COALESCE(MAX(position), 0) FROM hozuki_records WHERE collection='notifications'"
        )
        start_position = int(cur.fetchone()[0])
        notification_payload = []
        for offset, member in enumerate(members, start=1):
            row = {
                "notification_id": str(first_notification_id + offset - 1),
                "kind": "一般募集",
                "member_id": str(member.get("member_id", "")),
                "member_name": str(member.get("name", "")),
                "message": message,
                "created_at": created_at,
                "read_at": "",
                "batch_id": batch_id,
            }
            position = start_position + offset
            notification_payload.append({
                "record_key": _record_key("notifications", row, position),
                "position": position,
                "data": row,
            })

        if notification_payload:
            cur.execute(
                """
                INSERT INTO hozuki_records(collection, record_key, position, data)
                SELECT 'notifications', x.record_key, x.position, x.data
                FROM jsonb_to_recordset(%s::jsonb) AS x(record_key text, position integer, data jsonb)
                ON CONFLICT (collection, record_key)
                DO UPDATE SET position=EXCLUDED.position, data=EXCLUDED.data, updated_at=NOW()
                """,
                (json.dumps(notification_payload, ensure_ascii=False),),
            )

        cur.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM hozuki_records WHERE collection='notification_batches'"
        )
        batch_position = int(cur.fetchone()[0])
        batch_row = {
            "batch_id": batch_id,
            "recruit_count": str(count),
            "created_at": created_at,
            "status": "送信済",
        }
        cur.execute(
            """
            INSERT INTO hozuki_records(collection, record_key, position, data)
            VALUES('notification_batches', %s, %s, %s::jsonb)
            ON CONFLICT (collection, record_key)
            DO UPDATE SET position=EXCLUDED.position, data=EXCLUDED.data, updated_at=NOW()
            """,
            (_record_key("notification_batches", batch_row, batch_position), batch_position, json.dumps(batch_row, ensure_ascii=False)),
        )
        conn.commit()

    _clear_read_cache()
    return {"sent": True, "recruit_count": count, "member_count": len(members), "message": message}


def storage_label() -> str:
    return "Neon PostgreSQL" if using_postgres() else "ローカルCSV"
