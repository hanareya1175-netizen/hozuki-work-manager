from __future__ import annotations

from datetime import date, datetime
import json
import socket
import time
import urllib.error
import urllib.request
import streamlit as st

import csvdb
from common import MEMBER_STATUS_ACTIVE, RECRUIT_STATUS_OPEN, require_admin, show_header, normalize_text

UNREAD = ""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _active_members() -> list[dict[str, str]]:
    return [r for r in csvdb.read("members") if normalize_text(r.get("status")) in {"", MEMBER_STATUS_ACTIVE, "使用中"}]


def _append(member_id: str, member_name: str, kind: str, message: str, batch_id: str = "") -> None:
    csvdb.append("notifications", {
        "notification_id": csvdb.next_id("notifications", "notification_id"),
        "kind": kind, "member_id": member_id, "member_name": member_name,
        "message": message, "created_at": _now(), "read_at": "", "batch_id": batch_id,
    })


def create_individual_notification(member_id: str, member_name: str) -> None:
    _append(member_id, member_name, "個別依頼", "個別の作業依頼が1件あります。")


def _secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default)).strip()
    except Exception:
        return default


def _wake_push_service(base_url: str) -> None:
    """Wake a sleeping Render free service before the actual push request.

    Render free services can take tens of seconds to resume.  A separate health
    request avoids mixing that cold-start delay with the broadcast request.
    """
    health_req = urllib.request.Request(
        f"{base_url}/health",
        headers={"User-Agent": "HozukiWorks/Build212"},
        method="GET",
    )
    last_exc: Exception | None = None
    # First request may time out while Render is waking, but the wake-up itself
    # continues on the server.  Retry once after a short pause.
    for timeout in (70, 35):
        try:
            with urllib.request.urlopen(health_req, timeout=timeout) as res:
                if 200 <= res.status < 300:
                    return
        except Exception as exc:
            last_exc = exc
            time.sleep(2)
    if last_exc:
        raise last_exc


def _push_broadcast(*, kind: str, message: str) -> tuple[bool, str]:
    """Send one broadcast request to the separate HozukiWorks Push service.

    The network call occurs only when an administrator explicitly presses a
    send button, so normal page navigation does not wait on the push service.
    """
    base_url = _secret("PUSH_SERVICE_URL").rstrip("/")
    api_key = _secret("PUSH_API_KEY")
    app_url = _secret("HOZUKI_APP_URL")
    if not base_url or not api_key:
        return False, "プッシュ通知サービスが未設定です。PUSH_SERVICE_URL と PUSH_API_KEY を設定してください。"

    payload = {
        "kind": kind,
        "message": normalize_text(message),
        "target_url": app_url,
    }

    try:
        _wake_push_service(base_url)
    except Exception as exc:
        return False, f"プッシュ通知サービスの起動に失敗しました：{exc}"

    req = urllib.request.Request(
        f"{base_url}/api/broadcast",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
            "User-Agent": "HozukiWorks/Build212",
        },
        method="POST",
    )

    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=35) as res:
                body = json.loads(res.read().decode("utf-8") or "{}")
                sent = int(body.get("sent", 0) or 0)
                removed = int(body.get("removed", 0) or 0)
                failed = int(body.get("failed", 0) or 0)
                if 200 <= res.status < 300:
                    suffix_parts = []
                    if removed:
                        suffix_parts.append(f"無効端末{removed}件を整理")
                    if failed:
                        suffix_parts.append(f"送信失敗{failed}件")
                    suffix = f"（{'、'.join(suffix_parts)}）" if suffix_parts else ""
                    return True, f"スマホへ{sent}台送信しました。{suffix}"
            return False, "プッシュ通知サービスから正常な応答がありませんでした。"
        except (TimeoutError, socket.timeout) as exc:
            last_exc = exc
            if attempt == 0:
                time.sleep(2)
                continue
        except urllib.error.URLError as exc:
            last_exc = exc
            if attempt == 0:
                time.sleep(2)
                continue
        except Exception as exc:
            return False, f"プッシュ通知の送信に失敗しました：{exc}"

    return False, f"プッシュ通知の送信に失敗しました：{last_exc}"


def _send_batch() -> tuple[bool, str]:
    result = csvdb.send_general_notification_batch(
        open_status=RECRUIT_STATUS_OPEN,
        active_statuses={"", MEMBER_STATUS_ACTIVE, "使用中"},
        created_at=_now(),
    )
    if not result["sent"]:
        return False, "未通知の一般募集はありません。"

    # Android/iPhoneで着信確認しやすいよう、Pushの配送経路は
    # 管理者メッセージと同じ "message" に統一する。
    # 表示本文の先頭で「新規募集あり」と明示する。
    push_ok, push_msg = _push_broadcast(
        kind="message",
        message="【新規募集あり】新しい作業募集があります。HozukiWorksで確認してください。",
    )
    base = f"一般募集{result['recruit_count']}件を、まとめて1回通知しました。"
    if push_ok:
        return True, f"{base} {push_msg}"
    # The in-app notification batch is already safely recorded even if push is
    # temporarily unavailable; report that distinction to the administrator.
    return True, f"{base} ただしスマホ通知は送信できませんでした。{push_msg}"



def _same_member(row: dict[str, str], member_id: str, member_name: str) -> bool:
    """Match old and new view records reliably.

    Earlier versions sometimes stored only a member name, while newer versions
    store both ID and name.  Normalize both sides and accept either non-empty
    identifier so an already viewed recruit never becomes NEW again merely
    because the login representation changed.
    """
    row_member_id = normalize_text(row.get("member_id"))
    row_member_name = normalize_text(row.get("member_name"))
    member_id = normalize_text(member_id)
    member_name = normalize_text(member_name)
    return bool(
        (member_id and row_member_id and row_member_id == member_id)
        or (member_name and row_member_name and row_member_name == member_name)
    )


def _member_key(member_id: str, member_name: str) -> str:
    member_id = normalize_text(member_id)
    if member_id:
        return f"id:{member_id}"
    return f"name:{normalize_text(member_name).casefold()}"


def viewed_recruit_ids_for_member(member_id: str, member_name: str) -> set[str]:
    """Return persisted read IDs for one member with one focused DB query."""
    return csvdb.read_recruit_read_ids(
        _member_key(member_id, member_name),
        normalize_text(member_id),
        normalize_text(member_name),
    )


def new_recruit_ids_for_member(
    member_id: str,
    member_name: str,
    recruits: list[dict[str, str]] | None = None,
    viewed_ids: set[str] | None = None,
) -> set[str]:
    """Return NEW recruit IDs without re-reading data already loaded by the screen."""
    rows = recruits if recruits is not None else csvdb.read("recruit")
    viewed = viewed_ids if viewed_ids is not None else viewed_recruit_ids_for_member(member_id, member_name)
    today = date.today().isoformat()
    return {
        normalize_text(row.get("id"))
        for row in rows
        if normalize_text(row.get("id"))
        and normalize_text(row.get("notification_batch_id"))
        and normalize_text(row.get("status")) == RECRUIT_STATUS_OPEN
        and normalize_text(row.get("date")) >= today
        and normalize_text(row.get("id")) not in viewed
    }


def mark_recruit_detail_viewed(
    member_id: str,
    member_name: str,
    recruit_id: str,
    batch_id: str,
) -> None:
    """Mark exactly one recruit read with a deterministic one-query UPSERT."""
    recruit_id = normalize_text(recruit_id)
    if not recruit_id:
        return
    csvdb.mark_recruit_read({
        "member_key": _member_key(member_id, member_name),
        "member_id": normalize_text(member_id),
        "member_name": normalize_text(member_name),
        "recruit_id": recruit_id,
        "read_at": _now(),
    })

def mark_individual_notifications_read(member_id: str, member_name: str) -> int:
    """Mark all unread individual-work notifications for one member as read.

    Returns the number of notifications updated.  The helper is called when the
    member opens the assigned-work screen, so the home badge disappears without
    requiring a separate confirmation button.
    """
    rows = csvdb.read("notifications")
    now = _now()
    updated = 0
    for row in rows:
        if (
            not normalize_text(row.get("read_at"))
            and normalize_text(row.get("kind")) == "個別依頼"
            and _same_member(row, member_id, member_name)
        ):
            row["read_at"] = now
            updated += 1
    if updated:
        csvdb.write_all("notifications", rows)
    return updated


def notification_screen(*, role: str) -> None:
    if not require_admin(role):
        return
    show_header("通知")

    recruits = csvdb.read("recruit")
    pending = sum(
        1 for r in recruits
        if r.get("status") == RECRUIT_STATUS_OPEN
        and r.get("notification_status", "未通知") == "未通知"
    )

    st.subheader("新規募集あり")
    st.metric("未通知の一般募集", pending)
    st.caption("一般募集を何件か登録してから、まとめて1回だけスマホへ知らせます。募集の詳細はHozukiWorks本体で確認します。")
    if st.button(
        "📣 新規募集ありを通知",
        type="primary",
        use_container_width=True,
        disabled=pending == 0,
        key="push_general_recruits",
    ):
        ok, msg = _send_batch()
        (st.success if ok else st.info)(msg)

    st.divider()
    st.subheader("管理者からのお知らせ")
    st.caption("この文章はスマホの通知本文にそのまま表示されます。全員へ一斉配信します。")
    with st.form("admin_push_message_form", clear_on_submit=True):
        message = st.text_area(
            "通知メッセージ",
            placeholder="例：明日の収穫は雨天のため中止します。",
            max_chars=180,
            height=100,
        )
        submitted = st.form_submit_button(
            "📢 お知らせを送信",
            use_container_width=True,
        )
    if submitted:
        text = normalize_text(message)
        if not text:
            st.warning("通知メッセージを入力してください。")
        else:
            ok, msg = _push_broadcast(kind="message", message=text)
            (st.success if ok else st.error)(msg)

    setup_url = _secret("PUSH_SETUP_URL") or _secret("PUSH_SERVICE_URL")
    if setup_url:
        st.divider()
        st.caption("メンバー用の通知設定ページ")
        st.link_button("🔔 通知設定ページを開く", setup_url, use_container_width=True)

    st.divider()
    st.subheader("一般募集の通知履歴")
    batches = list(reversed(csvdb.read("notification_batches")))
    if not batches:
        st.info("一般募集の通知履歴はありません。")
    else:
        st.dataframe(
            [{
                "通知日時": r.get("created_at"),
                "募集件数": r.get("recruit_count"),
                "状態": r.get("status"),
            } for r in batches],
            hide_index=True,
            use_container_width=True,
        )




def member_notification_panel(*, member_id: str, member_name: str) -> None:
    """Show home messages from their actual source data, not duplicate state."""
    new_count = len(new_recruit_ids_for_member(member_id, member_name))

    rows = csvdb.read("notifications")
    individual_unread = [
        r for r in rows
        if not normalize_text(r.get("read_at"))
        and normalize_text(r.get("kind")) == "個別依頼"
        and _same_member(r, member_id, member_name)
    ]

    if new_count:
        st.warning(f"🔔 新しい作業募集が{new_count}件あります。")

    if individual_unread:
        st.warning(f"🔔 個別の作業依頼が{len(individual_unread)}件あります。")
        if st.button("個別通知を確認済みにする", use_container_width=True, key="mark_individual_notifications_read_button"):
            mark_individual_notifications_read(member_id, member_name)
            st.rerun()

    if not new_count and not individual_unread:
        st.caption("新しい通知はありません。")

    setup_url = _secret("PUSH_SETUP_URL") or _secret("PUSH_SERVICE_URL")
    if setup_url:
        st.link_button(
            "🔔 スマホ通知を設定する",
            setup_url,
            use_container_width=True,
        )

