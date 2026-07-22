from __future__ import annotations

from datetime import date, datetime
import json
import urllib.request
import streamlit as st
import streamlit.components.v1 as components

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


def _optional_webhook(message: str) -> tuple[bool, str]:
    try:
        url = str(st.secrets.get("PUSH_WEBHOOK_URL", "")).strip()
    except Exception:
        url = ""
    if not url:
        return False, "外部プッシュ通知は未設定です。アプリ内通知のみ登録しました。"
    try:
        req = urllib.request.Request(url, data=json.dumps({"message": message}, ensure_ascii=False).encode("utf-8"), headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as res:
            if 200 <= res.status < 300:
                return True, "スマホ通知の送信要求も完了しました。"
        return False, "外部プッシュ通知の送信に失敗しました。"
    except Exception as exc:
        return False, f"外部プッシュ通知の送信に失敗しました：{exc}"


def _send_batch() -> tuple[bool, str]:
    recruits = csvdb.read("recruit")
    targets = [r for r in recruits if r.get("status") == RECRUIT_STATUS_OPEN and r.get("notification_status", "未通知") == "未通知"]
    if not targets:
        return False, "未通知の一般募集はありません。"
    count = len(targets); message = f"新しい作業募集が{count}件あります。"
    batch_id = csvdb.next_id("notification_batches", "batch_id")
    members = _active_members()
    for member in members:
        _append(normalize_text(member.get("member_id")), normalize_text(member.get("name")), "一般募集", message, batch_id)
    for row in recruits:
        if row in targets:
            row["notification_status"] = "通知済"
            row["notification_batch_id"] = batch_id
    csvdb.write_all("recruit", recruits)
    csvdb.append("notification_batches", {"batch_id":batch_id,"recruit_count":str(count),"created_at":_now(),"status":"送信済"})
    _, extra = _optional_webhook(message)
    return True, f"一般募集{count}件を、まとめて1回通知しました。{extra}"



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


def new_recruit_ids_for_member(member_id: str, member_name: str) -> set[str]:
    """Return the single source of truth for general-recruit NEW state.

    A recruit is NEW for a member when it was included in a notification batch,
    is still open and current, and that member has not opened its detail yet.
    Home messages and recruit-list NEW markers both use this function directly.
    """
    viewed = {
        normalize_text(row.get("recruit_id"))
        for row in csvdb.read("recruit_views")
        if _same_member(row, member_id, member_name)
    }
    today = date.today().isoformat()
    result: set[str] = set()
    for row in csvdb.read("recruit"):
        recruit_id = normalize_text(row.get("id"))
        if (
            recruit_id
            and normalize_text(row.get("notification_batch_id"))
            and normalize_text(row.get("status")) == RECRUIT_STATUS_OPEN
            and normalize_text(row.get("date")) >= today
            and recruit_id not in viewed
        ):
            result.add(recruit_id)
    return result


def mark_recruit_detail_viewed(member_id: str, member_name: str, recruit_id: str) -> None:
    """Record the one fact that drives NEW state: this member opened this detail."""
    recruit_id = normalize_text(recruit_id)
    if not recruit_id:
        return
    target = next(
        (r for r in csvdb.read("recruit") if normalize_text(r.get("id")) == recruit_id),
        None,
    )
    if not target:
        return
    batch_id = normalize_text(target.get("notification_batch_id"))
    if not batch_id:
        return

    views = csvdb.read("recruit_views")
    already = any(
        _same_member(r, member_id, member_name)
        and normalize_text(r.get("recruit_id")) == recruit_id
        for r in views
    )
    if already:
        return
    views.append({
        "member_id": member_id,
        "member_name": member_name,
        "recruit_id": recruit_id,
        "batch_id": batch_id,
        "seen_at": _now(),
    })
    csvdb.write_all("recruit_views", views)


def notification_screen(*, role: str) -> None:
    if not require_admin(role): return
    show_header("通知")
    recruits = csvdb.read("recruit")
    pending = sum(1 for r in recruits if r.get("status") == RECRUIT_STATUS_OPEN and r.get("notification_status", "未通知") == "未通知")
    st.metric("未通知の一般募集", pending)
    st.caption("一般募集を何件か登録してから、まとめて1回だけ通知します。通知内容は募集件数だけです。")
    if st.button("まとめて通知する", type="primary", use_container_width=True, disabled=pending == 0):
        ok, msg = _send_batch(); (st.success if ok else st.info)(msg); st.rerun()
    st.divider()
    st.subheader("通知履歴")
    batches = list(reversed(csvdb.read("notification_batches")))
    if not batches: st.info("一般募集の通知履歴はありません。")
    else: st.dataframe([{"通知日時":r.get("created_at"),"募集件数":r.get("recruit_count"),"状態":r.get("status")} for r in batches], hide_index=True, use_container_width=True)


def _browser_permission_widget() -> None:
    components.html("""
    <button id="notify" style="width:100%;min-height:48px;font-size:16px;font-weight:700;border-radius:10px;border:1px solid #aaa;background:white">スマホ通知を有効にする</button>
    <div id="msg" style="margin-top:6px;font-size:14px"></div>
    <script>
    const b=document.getElementById('notify'), m=document.getElementById('msg');
    b.onclick=async()=>{ if(!('Notification' in window)){m.textContent='このブラウザは通知に対応していません。';return;} const p=await Notification.requestPermission(); m.textContent=p==='granted'?'通知を有効にしました。':'通知が許可されませんでした。'; if(p==='granted') new Notification('HozukiWorks',{body:'通知テストです。'}); };
    </script>""", height=80)


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
        if st.button("個別通知を確認済みにする", use_container_width=True, key="mark_individual_notifications_read"):
            now = _now()
            for row in rows:
                if (
                    not normalize_text(row.get("read_at"))
                    and normalize_text(row.get("kind")) == "個別依頼"
                    and _same_member(row, member_id, member_name)
                ):
                    row["read_at"] = now
            csvdb.write_all("notifications", rows)
            st.rerun()

    if not new_count and not individual_unread:
        st.caption("新しい通知はありません。")

