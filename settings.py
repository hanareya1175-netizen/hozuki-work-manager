from __future__ import annotations

import streamlit as st

from common import require_admin, show_header
from master_data import ACTIVE, INACTIVE, add_master, read_master, update_master
from members import members_screen


def settings_screen(*, role: str) -> None:
    if not require_admin(role):
        return
    show_header("設定")
    st.caption("メンバー、圃場、作業区分を管理します。使用停止にしても過去のデータは残ります。")
    category = st.radio(
        "設定項目",
        ["メンバー", "圃場", "作業区分"],
        horizontal=True,
        key="settings_category",
    )
    st.divider()
    if category == "メンバー":
        _members(role)
    elif category == "圃場":
        _master("places", "圃場・場所")
    else:
        _master("worktypes", "作業区分")


def _members(role: str) -> None:
    action = st.radio(
        "操作",
        ["一覧", "新規登録", "編集"],
        horizontal=True,
        key="settings_member_action",
    )
    mode = {"一覧": "list", "新規登録": "create", "編集": "edit"}[action]
    members_screen(role=role, mode=mode, embedded=True)


def _master(kind: str, label: str) -> None:
    rows = read_master(kind)
    action = st.radio(
        "操作",
        ["一覧", "新規登録", "編集"],
        horizontal=True,
        key=f"settings_{kind}_action",
    )

    if action == "一覧":
        if not rows:
            st.info(f"{label}は登録されていません。")
            return
        st.dataframe(
            [{"名称": r["name"], "状態": r["status"], "表示順": int(r["sort_order"])} for r in rows],
            use_container_width=True,
            hide_index=True,
        )
        return

    if action == "新規登録":
        with st.form(f"{kind}_create_form", clear_on_submit=True):
            name = st.text_input("名称")
            submitted = st.form_submit_button("登録", use_container_width=True)
        if submitted:
            ok, message = add_master(kind, name)
            (st.success if ok else st.error)(message)
            if ok:
                st.rerun()
        return

    if not rows:
        st.info(f"編集できる{label}がありません。")
        return
    ids = [r["id"] for r in rows]
    item_id = st.selectbox(
        f"編集する{label}",
        ids,
        format_func=lambda x: next(r["name"] for r in rows if r["id"] == x),
        key=f"{kind}_edit_select",
    )
    row = next(r for r in rows if r["id"] == item_id)
    with st.form(f"{kind}_edit_form_{item_id}"):
        name = st.text_input("名称", value=row["name"])
        status = st.radio(
            "状態",
            [ACTIVE, INACTIVE],
            index=0 if row["status"] == ACTIVE else 1,
            horizontal=True,
        )
        sort_order = st.number_input("表示順", min_value=1, step=1, value=int(row["sort_order"]))
        submitted = st.form_submit_button("変更を保存", use_container_width=True)
    if submitted:
        ok, message = update_master(kind, item_id, name, status, int(sort_order))
        (st.success if ok else st.error)(message)
        if ok:
            st.rerun()
