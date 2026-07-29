from __future__ import annotations
from datetime import date, datetime
import streamlit as st
import csvdb
from notifications import create_individual_notification, new_recruit_ids_for_member, mark_recruit_detail_viewed, mark_individual_notifications_read
from master_data import active_names
from common import (
    MEMBER_STATUS_ACTIVE, PLACES, RECRUIT_STATUS_ACCEPTED,
    RECRUIT_STATUS_ADMIN, RECRUIT_STATUS_ASSIGNED, RECRUIT_STATUS_CANCELLED,
    RECRUIT_STATUS_COMPLETED, RECRUIT_STATUS_OPEN, ROLE_MEMBER,
    WORK_TYPES, format_date, normalize_role, normalize_text,
    require_admin, show_header,
)

ACTIVE_STATUSES = {
    RECRUIT_STATUS_OPEN, RECRUIT_STATUS_ACCEPTED,
    RECRUIT_STATUS_ASSIGNED, RECRUIT_STATUS_ADMIN,
}


def recruit_screen(*, role: str, member_name: str, member_id: str = "", mode: str) -> None:
    if mode == "create":
        if require_admin(role):
            _create(member_name, member_id)
    elif mode == "edit":
        if require_admin(role):
            _edit()
    elif mode == "duplicate":
        if require_admin(role):
            _duplicate(member_name, member_id)
    elif mode == "admin_list":
        if require_admin(role):
            _admin_list()
    elif mode == "open_list":
        _open_list(member_name, member_id)
    elif mode == "my_list":
        _my_list(member_name, member_id)
    else:
        st.error("募集画面の指定が不正です。")


def _active_members() -> list[dict[str, str]]:
    rows = [
        row for row in csvdb.read("members")
        if normalize_text(row.get("status")) == MEMBER_STATUS_ACTIVE
        and normalize_role(row.get("role")) == ROLE_MEMBER
    ]
    rows.sort(key=lambda row: normalize_text(row.get("name")))
    return rows


def _worktypes() -> list[str]:
    return active_names("worktypes") or WORK_TYPES


def _places() -> list[str]:
    return active_names("places") or PLACES


def _safe_date(value: object, fallback: date | None = None) -> date:
    fallback = fallback or date.today()
    try:
        return datetime.strptime(normalize_text(value), "%Y-%m-%d").date()
    except ValueError:
        return fallback


def _safe_time(value: object):
    text = normalize_text(value)
    try:
        return datetime.strptime(text, "%H:%M").time()
    except ValueError:
        return datetime.strptime("08:00", "%H:%M").time()


def _registration_type(row: dict[str, str]) -> str:
    status = normalize_text(row.get("status"))
    if status == RECRUIT_STATUS_ADMIN:
        return "管理者作業"
    if status == RECRUIT_STATUS_ASSIGNED:
        return "指名依頼"
    return "一般募集"


def _assignment(register_type: str, selected_member_id: str, members: list[dict[str, str]], admin_name: str, admin_id: str) -> tuple[str, str, str]:
    if register_type == "指名依頼":
        selected = next(
            row for row in members
            if normalize_text(row.get("member_id")) == selected_member_id
        )
        return (
            RECRUIT_STATUS_ASSIGNED,
            normalize_text(selected.get("member_id")),
            normalize_text(selected.get("name")),
        )
    if register_type == "管理者作業":
        return RECRUIT_STATUS_ADMIN, admin_id, admin_name
    return RECRUIT_STATUS_OPEN, "", ""


def _create(admin_name: str, admin_id: str) -> None:
    show_header("作業登録")
    st.caption("一般募集、特定作業者への指名依頼、管理者自身の作業を登録できます。")

    message = st.session_state.pop("recruit_create_message", "")
    if message:
        st.success(message)

    register_type = st.radio(
        "登録方法", ["一般募集", "指名依頼", "管理者作業"],
        horizontal=True, key="recruit_register_type",
    )
    members = _active_members()
    selected_member_id = ""
    if register_type == "指名依頼":
        if not members:
            st.warning("指名できる有効なメンバーが登録されていません。")
            return
        member_ids = [normalize_text(row.get("member_id")) for row in members]
        selected_member_id = st.selectbox(
            "作業者", member_ids,
            format_func=lambda mid: next(
                normalize_text(row.get("name")) for row in members
                if normalize_text(row.get("member_id")) == mid
            ), key="assigned_member_select",
        )
    elif register_type == "管理者作業":
        st.info(f"担当者：{admin_name}（管理者）")

    with st.form("recruit_create", enter_to_submit=False):
        work_date = st.date_input("作業日", value=None, min_value=date.today(), key="create_work_date")
        work_type = st.selectbox("作業区分", _worktypes(), index=None, placeholder="選択してください", key="create_work_type")
        place = st.selectbox("場所", _places(), index=None, placeholder="選択してください", key="create_place")
        detail = st.text_input("内容・畝番号など", key="create_detail")
        use_time = st.checkbox("時間を指定する", key="create_use_time")
        col1, col2 = st.columns(2)
        with col1:
            start = st.time_input("開始時刻", key="create_start")
        with col2:
            end = st.time_input("終了時刻", key="create_end")
        continuous = st.checkbox(
            "登録後も入力内容を残して続けて登録する",
            value=False, key="create_continuous",
        )
        submitted = st.form_submit_button("登録", use_container_width=True)

    if not submitted:
        return
    if work_date is None or not work_type or not place:
        st.error("作業日・作業区分・場所を入力してください。")
        return
    if use_time and end <= start:
        st.error("終了時刻は開始時刻より後にしてください。")
        return

    status, assigned_id, assigned_name = _assignment(
        register_type, selected_member_id, members, admin_name, admin_id
    )
    csvdb.append("recruit", {
        "id": csvdb.next_id("recruit", "id"),
        "date": work_date.isoformat(), "type": work_type, "place": place,
        "detail": detail.strip(),
        "start": start.strftime("%H:%M") if use_time else "",
        "end": end.strftime("%H:%M") if use_time else "",
        "status": status, "member_id": assigned_id, "member": assigned_name,
        "notification_status": "未通知" if status == RECRUIT_STATUS_OPEN else ("個別通知済" if status == RECRUIT_STATUS_ASSIGNED else "対象外"),
    })
    if status == RECRUIT_STATUS_ASSIGNED:
        create_individual_notification(assigned_id, assigned_name)

    messages = {
        "一般募集": "一般募集を登録しました。",
        "指名依頼": f"{assigned_name}さんへの指名依頼を登録しました。",
        "管理者作業": "管理者作業を登録しました。",
    }
    st.session_state["recruit_create_message"] = messages[register_type] + (" 続けて登録できます。" if continuous else "")
    if not continuous:
        for key in (
            "recruit_register_type", "assigned_member_select", "create_work_date",
            "create_work_type", "create_place", "create_detail", "create_use_time",
            "create_start", "create_end", "create_continuous",
        ):
            st.session_state.pop(key, None)
    st.rerun()


def _edit(recruit_id: str | None = None, *, embedded: bool = False) -> None:
    if not embedded:
        show_header("募集編集")
    rows = csvdb.read("recruit")
    if not rows:
        st.info("募集は登録されていません。")
        return

    rows.sort(key=lambda x: (x.get("date", ""), int(x.get("id") or 0)))
    ids = [row.get("id", "") for row in rows]
    if recruit_id is None:
        recruit_id = st.selectbox(
            "編集する募集", ids, index=None, placeholder="募集を選択してください",
            format_func=lambda rid: next(
                f"{rid}：{_summary(row)}｜{row.get('status', '')}"
                for row in rows if row.get("id") == rid
            ), key="edit_recruit_select",
        )
        if not recruit_id:
            return
    row = next(item for item in rows if item.get("id") == recruit_id)
    if row.get("status") == RECRUIT_STATUS_COMPLETED:
        st.info("完了済み募集を編集すると、実績一覧側の作業日・作業区分・担当者は自動変更されません。")

    worktypes = _worktypes()
    current_type = normalize_text(row.get("type"))
    if current_type and current_type not in worktypes:
        worktypes.append(current_type)
    places = _places()
    current_place = normalize_text(row.get("place"))
    if current_place and current_place not in places:
        places.append(current_place)
    use_time_default = bool(normalize_text(row.get("start")))

    with st.form(f"recruit_edit_{recruit_id}", enter_to_submit=False):
        work_date = st.date_input("作業日", value=_safe_date(row.get("date")))
        work_type = st.selectbox("作業区分", worktypes, index=worktypes.index(current_type))
        place = st.selectbox("場所", places, index=places.index(current_place))
        detail = st.text_input("内容・畝番号など", value=normalize_text(row.get("detail")))
        use_time = st.checkbox("時間を指定する", value=use_time_default)
        col1, col2 = st.columns(2)
        with col1:
            start = st.time_input("開始時刻", value=_safe_time(row.get("start")))
        with col2:
            end = st.time_input("終了時刻", value=_safe_time(row.get("end")) if row.get("end") else datetime.strptime("16:00", "%H:%M").time())
        submitted = st.form_submit_button("変更を保存", use_container_width=True)

    if not submitted:
        return
    if use_time and end <= start:
        st.error("終了時刻は開始時刻より後にしてください。")
        return

    for item in rows:
        if item.get("id") == recruit_id:
            item.update({
                "date": work_date.isoformat(), "type": work_type, "place": place,
                "detail": detail.strip(),
                "start": start.strftime("%H:%M") if use_time else "",
                "end": end.strftime("%H:%M") if use_time else "",
            })
            break
    csvdb.write_all("recruit", rows)
    st.success("募集内容を更新しました。")


def _duplicate(admin_name: str, admin_id: str) -> None:
    show_header("募集複製")
    rows = csvdb.read("recruit")
    if not rows:
        st.info("複製できる募集はありません。")
        return
    rows.sort(key=lambda x: (x.get("date", ""), int(x.get("id") or 0)), reverse=True)
    source_id = st.selectbox(
        "複製元の募集", [row.get("id", "") for row in rows],
        format_func=lambda rid: next(
            f"{rid}：{_summary(row)}｜{row.get('status', '')}"
            for row in rows if row.get("id") == rid
        ), key="duplicate_source_select",
    )
    source = next(row for row in rows if row.get("id") == source_id)
    members = _active_members()
    default_type = _registration_type(source)
    register_types = ["一般募集", "指名依頼", "管理者作業"]
    register_type = st.radio(
        "複製後の登録方法", register_types,
        index=register_types.index(default_type), horizontal=True,
    )

    selected_member_id = ""
    if register_type == "指名依頼":
        if not members:
            st.warning("指名できる有効なメンバーが登録されていません。")
            return
        member_ids = [normalize_text(row.get("member_id")) for row in members]
        current_id = normalize_text(source.get("member_id"))
        default_index = member_ids.index(current_id) if current_id in member_ids else 0
        selected_member_id = st.selectbox(
            "作業者", member_ids, index=default_index,
            format_func=lambda mid: next(
                normalize_text(row.get("name")) for row in members
                if normalize_text(row.get("member_id")) == mid
            ), key="duplicate_member_select",
        )
    elif register_type == "管理者作業":
        st.info(f"担当者：{admin_name}（管理者）")

    worktypes = _worktypes()
    source_type = normalize_text(source.get("type"))
    if source_type not in worktypes:
        worktypes.append(source_type)
    places = _places()
    source_place = normalize_text(source.get("place"))
    if source_place not in places:
        places.append(source_place)
    use_time_default = bool(normalize_text(source.get("start")))

    with st.form("recruit_duplicate"):
        work_date = st.date_input("新しい作業日", value=max(date.today(), _safe_date(source.get("date"))), min_value=date.today())
        work_type = st.selectbox("作業区分", worktypes, index=worktypes.index(source_type))
        place = st.selectbox("場所", places, index=places.index(source_place))
        detail = st.text_input("内容・畝番号など", value=normalize_text(source.get("detail")))
        use_time = st.checkbox("時間を指定する", value=use_time_default)
        col1, col2 = st.columns(2)
        with col1:
            start = st.time_input("開始時刻", value=_safe_time(source.get("start")))
        with col2:
            end = st.time_input("終了時刻", value=_safe_time(source.get("end")) if source.get("end") else datetime.strptime("16:00", "%H:%M").time())
        submitted = st.form_submit_button("複製して登録", use_container_width=True)

    if not submitted:
        return
    if use_time and end <= start:
        st.error("終了時刻は開始時刻より後にしてください。")
        return
    status, assigned_id, assigned_name = _assignment(
        register_type, selected_member_id, members, admin_name, admin_id
    )
    csvdb.append("recruit", {
        "id": csvdb.next_id("recruit", "id"),
        "date": work_date.isoformat(), "type": work_type, "place": place,
        "detail": detail.strip(),
        "start": start.strftime("%H:%M") if use_time else "",
        "end": end.strftime("%H:%M") if use_time else "",
        "status": status, "member_id": assigned_id, "member": assigned_name,
        "notification_status": "未通知" if status == RECRUIT_STATUS_OPEN else ("個別通知済" if status == RECRUIT_STATUS_ASSIGNED else "対象外"),
    })
    if status == RECRUIT_STATUS_ASSIGNED:
        create_individual_notification(assigned_id, assigned_name)
    st.success("募集を複製して新規登録しました。")


def _display_place(value: str) -> str:
    return {"第1圃場": "A畑", "第2圃場": "B畑", "第3圃場": "C畑", "選別作業場": "選別作業所"}.get(value, value)


def _time_text(row: dict[str, str]) -> str:
    return f"{row.get('start')}～{row.get('end')}" if row.get("start") else "指定なし"


def _detail(row: dict[str, str], *, show_status: bool = True) -> None:
    st.write(f"**作業日：** {format_date(row.get('date'))}")
    st.write(f"**作業区分：** {row.get('type', '')}")
    st.write(f"**場所：** {_display_place(row.get('place', ''))}")
    st.write(f"**時間：** {_time_text(row)}")
    if row.get("detail"):
        st.write(f"**内容：** {row.get('detail')}")
    if row.get("member"):
        st.write(f"**担当：** {row.get('member')}")
    if show_status:
        st.caption(f"募集番号：{row.get('id')}　状態：{row.get('status')}")


def _summary(row: dict[str, str]) -> str:
    return f"No.{row.get('id', '')}｜{format_date(row.get('date'))}｜{row.get('type', '')}｜場所：{_display_place(row.get('place', ''))}"


def _table_rows(rows: list[dict[str, str]], *, include_member: bool = True) -> list[dict[str, str]]:
    data = []
    for row in rows:
        item = {
            "番号": row.get("id", ""), "日付": format_date(row.get("date")),
            "作業": row.get("type", ""), "場所": _display_place(row.get("place", "")),
            "時間": _time_text(row), "内容": row.get("detail", ""), "状態": row.get("status", ""),
        }
        if include_member:
            item["担当"] = row.get("member", "")
        data.append(item)
    return data


def _cancel(recruit_id: str) -> None:
    rows = csvdb.read("recruit")
    for item in rows:
        if item.get("id") == recruit_id:
            item["status"] = RECRUIT_STATUS_CANCELLED
            break
    csvdb.write_all("recruit", rows)
    st.rerun()


def _admin_list() -> None:
    show_header("募集一覧・編集・取消")
    all_rows = sorted(csvdb.read("recruit"), key=lambda x: (x.get("date", ""), int(x.get("id") or 0)))
    if not all_rows:
        st.info("募集は登録されていません。")
        return
    opts = ["すべて", RECRUIT_STATUS_OPEN, RECRUIT_STATUS_ACCEPTED, RECRUIT_STATUS_ASSIGNED,
            RECRUIT_STATUS_ADMIN, RECRUIT_STATUS_COMPLETED, RECRUIT_STATUS_CANCELLED]
    selected = st.radio("表示するステータス", opts, horizontal=True, key="admin_recruit_status_filter")
    rows = all_rows if selected == "すべて" else [x for x in all_rows if x.get("status") == selected]
    st.caption(f"該当件数：{len(rows)}件")
    if not rows:
        st.info(f"「{selected}」の募集はありません。")
        return

    with st.container(key="desktop_only"):
        st.dataframe(_table_rows(rows), use_container_width=True, hide_index=True)
        selected_id = st.selectbox(
            "操作する募集", [r.get("id", "") for r in rows],
            index=None, placeholder="募集を選択してください",
            format_func=lambda x: next(_summary(r) for r in rows if r.get("id") == x),
            key="desktop_admin_recruit_select",
        )
        if selected_id:
            action = st.radio("操作", ["編集", "取消"], horizontal=True, key="desktop_admin_recruit_action")
            if action == "編集":
                st.divider()
                _edit(selected_id, embedded=True)
            else:
                target = next(r for r in rows if r.get("id") == selected_id)
                if target.get("status") in ACTIVE_STATUSES:
                    if st.button("選択した募集を取消", key="desktop_cancel_button", use_container_width=True):
                        _cancel(selected_id)
                else:
                    st.info("この募集は取消できる状態ではありません。")

    with st.container(key="mobile_only"):
        for row in rows:
            with st.expander(_summary(row)):
                _detail(row)
                action = st.radio("操作", ["表示のみ", "編集", "取消"], horizontal=True, key=f"mobile_action_{row.get('id')}")
                if action == "編集":
                    _edit(row.get("id", ""), embedded=True)
                elif action == "取消":
                    if row.get("status") in ACTIVE_STATUSES:
                        if st.button("募集を取消", key=f"mobile_cancel_{row.get('id')}", use_container_width=True):
                            _cancel(row.get("id", ""))
                    else:
                        st.info("この募集は取消できる状態ではありません。")


def _accept(recruit_id: str, member_name: str, member_id: str) -> None:
    rows = csvdb.read("recruit")
    target = None
    for item in rows:
        if item.get("id") == recruit_id and item.get("status") == RECRUIT_STATUS_OPEN:
            item["status"] = RECRUIT_STATUS_ACCEPTED
            item["member_id"] = member_id
            item["member"] = member_name
            target = item
            break
    csvdb.write_all("recruit", rows)
    if target:
        st.session_state["accept_message"] = f"{format_date(target.get('date'))}の「{target.get('type', '')}」を引受けました。"
    st.rerun()


def _toggle_mobile_recruit_detail(
    member_id: str,
    member_name: str,
    recruit_id: str,
    batch_id: str,
) -> None:
    """Toggle one detail and bind viewed state to the recruit ID itself."""
    recruit_id = normalize_text(recruit_id)
    current_id = normalize_text(st.session_state.get("mobile_recruit_detail_id"))

    if current_id == recruit_id:
        st.session_state["mobile_recruit_detail_id"] = ""
        return

    # Update the current browser session first.  The next render therefore
    # removes NEW from this exact number even before a remote DB read returns.
    viewed_now = set(st.session_state.get("viewed_recruit_ids_session", []))
    viewed_now.add(recruit_id)
    st.session_state["viewed_recruit_ids_session"] = sorted(viewed_now)
    st.session_state["mobile_recruit_detail_id"] = recruit_id

    # Persist with a single insert; no whole-table rewrite and no recruit reread.
    mark_recruit_detail_viewed(member_id, member_name, recruit_id, batch_id)


def _open_list(member_name: str, member_id: str) -> None:
    msg = st.session_state.pop("accept_message", "")
    if msg:
        st.success(msg)

    rows = [
        x for x in csvdb.read("recruit")
        if x.get("status") == RECRUIT_STATUS_OPEN
        and x.get("date", "") >= date.today().isoformat()
    ]

    # Always keep one stable chronological order.  NEW affects only the label,
    # never row position; therefore it cannot appear to jump to another number.
    rows.sort(key=lambda x: (x.get("date", ""), int(x.get("id") or 0)))

    persisted_new_ids = {
        normalize_text(rid)
        for rid in new_recruit_ids_for_member(member_id, member_name)
    }
    viewed_this_session = {
        normalize_text(rid)
        for rid in st.session_state.get("viewed_recruit_ids_session", [])
    }
    new_ids = persisted_new_ids - viewed_this_session
    selected_id = normalize_text(st.session_state.get("mobile_recruit_detail_id"))

    if not rows:
        st.info("現在募集中の作業はありません。")
        return

    new_rows = [r for r in rows if normalize_text(r.get("id")) in new_ids]
    other_rows = [r for r in rows if normalize_text(r.get("id")) not in new_ids]
    with st.container(key="desktop_only"):
        if new_rows:
            st.subheader(f"NEW　新しい募集（{len(new_rows)}件）")
            st.dataframe(_table_rows(new_rows, include_member=False), use_container_width=True, hide_index=True)
        if other_rows:
            if new_rows:
                st.subheader("その他の募集")
            st.dataframe(_table_rows(other_rows, include_member=False), use_container_width=True, hide_index=True)
        rid = st.selectbox(
            "引受ける作業", [normalize_text(r.get("id")) for r in rows],
            format_func=lambda x: next(
                (("NEW　" if normalize_text(r.get("id")) in new_ids else "") + _summary(r))
                for r in rows if normalize_text(r.get("id")) == normalize_text(x)
            ), key="desktop_accept_select",
        )
        if st.button("選択した作業を引受け", use_container_width=True, key="desktop_accept_button"):
            _accept(rid, member_name, member_id)

    with st.container(key="mobile_only"):
        for row in rows:
            row_id = normalize_text(row.get("id"))
            is_new = row_id in new_ids
            label = (("NEW　" if is_new else "") + _summary(row))
            st.button(
                label,
                key=f"mobile_detail_{row_id}",
                use_container_width=True,
                on_click=_toggle_mobile_recruit_detail,
                args=(
                    member_id, member_name, row_id,
                    normalize_text(row.get("notification_batch_id")),
                ),
            )

            if selected_id == row_id:
                with st.container(border=True):
                    _detail(row, show_status=False)
                    if st.button("引受け", key=f"mobile_accept_{row_id}", use_container_width=True):
                        _accept(row_id, member_name, member_id)


def _result_for_recruit(recruit_id: str):
    return next((x for x in csvdb.read("results") if x.get("recruit_id") == recruit_id), None)


def _show_result(result: dict[str, str]) -> None:
    st.write(f"**実績：** {result.get('result_value', '')} {result.get('unit', '')}".rstrip())
    if result.get("take_home_qty") not in {"", None, "0", "0.0"}:
        st.write(f"**持帰り支給量：** {result.get('take_home_qty')} kg")
    if result.get("note"):
        st.caption(f"備考：{result.get('note')}")


def _my_table_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    data = []
    for row in rows:
        result = _result_for_recruit(row.get("id", ""))
        value = f"{result.get('result_value', '')} {result.get('unit', '')}" if result else ""
        data.append({"No": row.get("id", ""), "日付": format_date(row.get("date")), "作業": row.get("type", ""), "場所": _display_place(row.get("place", "")), "時間": _time_text(row), "状態": row.get("status", ""), "実績": value})
    return data


def _my_list(member_name: str, member_id: str) -> None:
    show_header("自分の引受け作業")
    mark_individual_notifications_read(member_id, member_name)
    all_rows = [x for x in csvdb.read("recruit") if (x.get("member_id") == member_id or x.get("member") == member_name) and x.get("status") in {RECRUIT_STATUS_ACCEPTED, RECRUIT_STATUS_ASSIGNED, RECRUIT_STATUS_ADMIN, RECRUIT_STATUS_COMPLETED}]
    all_rows.sort(key=lambda x: (x.get("date", ""), int(x.get("id") or 0)))
    group = st.radio("表示する作業", ["引受け中", "完了"], horizontal=True, key="member_my_recruit_filter")
    active_statuses = {RECRUIT_STATUS_ACCEPTED, RECRUIT_STATUS_ASSIGNED, RECRUIT_STATUS_ADMIN}
    rows = [x for x in all_rows if x.get("status") in active_statuses] if group == "引受け中" else [x for x in all_rows if x.get("status") == RECRUIT_STATUS_COMPLETED]
    st.caption(f"該当件数：{len(rows)}件")
    if not rows:
        st.info(f"{group}の作業はありません。")
        return
    with st.container(key="desktop_only"):
        st.dataframe(_my_table_rows(rows), use_container_width=True, hide_index=True)
    with st.container(key="mobile_only"):
        for row in rows:
            with st.expander(_summary(row)):
                _detail(row)
                result = _result_for_recruit(row.get("id", ""))
                if result:
                    st.markdown("**登録実績**")
                    _show_result(result)
                elif row.get("status") == RECRUIT_STATUS_COMPLETED:
                    st.caption("実績データはまだ登録されていません。")
