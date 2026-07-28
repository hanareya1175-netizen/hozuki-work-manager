from __future__ import annotations
import streamlit as st
import csvdb
from common import (
    APP_ICON, APP_NAME, APP_SUBTITLE, APP_VERSION,
    RECRUIT_STATUS_ACCEPTED, RECRUIT_STATUS_ASSIGNED, RECRUIT_STATUS_ADMIN, RECRUIT_STATUS_OPEN,
    ROLE_ADMIN, ROLE_MEMBER, normalize_role, set_page_config,
    show_header, show_sidebar_user,
)
from login import current_user, is_logged_in, login_screen, logout_button
from members import members_screen
from recruit import recruit_screen
from results import results_screen
from settings import settings_screen
from notifications import notification_screen, member_notification_panel
from data_admin import data_admin_screen

ADMIN_MENU = [
    "ホーム", "募集登録", "募集一覧・編集・取消",
    "設定", "通知", "データ管理",
    "作業実績入力", "作業実績一覧", "作業実績編集",
]
MEMBER_MENU = ["ホーム", "募集中", "引受け作業"]

def count_recruits(status: str, rows: list[dict[str, str]] | None = None) -> int:
    rows = rows if rows is not None else csvdb.read("recruit")
    return sum(1 for x in rows if x.get("status") == status)

def admin_home(name: str) -> None:
    show_header(APP_NAME)
    st.success(f"{name} さん、管理者としてログインしています。")
    recruits = csvdb.read("recruit")
    a, b = st.columns(2)
    with a:
        st.metric("募集中", count_recruits(RECRUIT_STATUS_OPEN, recruits))
        st.metric("会員数", len(csvdb.read("members")))
    with b:
        st.metric("担当決定", count_recruits(RECRUIT_STATUS_ACCEPTED, recruits) + count_recruits(RECRUIT_STATUS_ASSIGNED, recruits) + count_recruits(RECRUIT_STATUS_ADMIN, recruits))
        st.metric("実績数", len(csvdb.read("results")))

    st.divider()
    if st.button("ログアウト", use_container_width=True, key="admin_logout_home"):
        st.session_state.clear()
        st.rerun()

def member_home(name: str, member_id: str) -> None:
    show_header(APP_NAME)
    st.success(f"{name} さん、ようこそ。")
    recruits = csvdb.read("recruit")
    my_active = sum(
        1 for x in recruits
        if (x.get("member_id") == member_id or x.get("member") == name)
        and x.get("status") in {RECRUIT_STATUS_ACCEPTED, RECRUIT_STATUS_ASSIGNED, RECRUIT_STATUS_ADMIN}
    )
    a, b = st.columns(2)
    with a:
        st.metric("募集中", count_recruits(RECRUIT_STATUS_OPEN, recruits))
    with b:
        st.metric("引受け中", my_active)
    member_notification_panel(member_id=member_id, member_name=name)
    st.info("上のメニューから、募集中の作業または引受けた作業を確認できます。")

    st.divider()
    member_logout_button()

def admin_navigation() -> str:
    return st.selectbox(
        "管理者メニュー",
        ADMIN_MENU,
        key="admin_main_menu",
    )

def member_navigation() -> str:
    st.caption("メンバーメニュー")
    return st.radio(
        "メンバーメニュー",
        MEMBER_MENU,
        horizontal=True,
        label_visibility="collapsed",
        key="member_main_menu",
    )

def member_logout_button() -> None:
    if st.button("ログアウト", use_container_width=True, key="member_logout_main"):
        st.session_state.clear()
        st.rerun()

def main() -> None:
    set_page_config()
    csvdb.initialize()

    if not is_logged_in():
        login_screen()
        return

    user = current_user()
    name = user.get("name", "")
    member_id = user.get("member_id", "")
    role = normalize_role(user.get("role"))

    show_sidebar_user(name, role)
    st.sidebar.divider()
    logout_button()

    if role == ROLE_ADMIN:
        menu = admin_navigation()
        st.divider()

        if menu == "ホーム":
            admin_home(name)
        elif menu == "募集登録":
            recruit_screen(role=role, member_name=name, member_id=member_id, mode="create")
        elif menu == "募集一覧・編集・取消":
            recruit_screen(role=role, member_name=name, member_id=member_id, mode="admin_list")
        elif menu == "設定":
            settings_screen(role=role)
        elif menu == "通知":
            notification_screen(role=role)
        elif menu == "データ管理":
            data_admin_screen(role=role)
        elif menu == "作業実績入力":
            results_screen(role=role, mode="create")
        elif menu == "作業実績一覧":
            results_screen(role=role, mode="list")
        elif menu == "作業実績編集":
            results_screen(role=role, mode="edit")

        return

    if role == ROLE_MEMBER:
        menu = member_navigation()
        st.divider()
        if menu == "募集中":
            recruit_screen(
                role=role, member_name=name, member_id=member_id, mode="open_list"
            )
        elif menu == "引受け作業":
            recruit_screen(
                role=role, member_name=name, member_id=member_id, mode="my_list"
            )
        else:
            member_home(name, member_id)

        return

    st.error("権限設定が不正です。")

if __name__ == "__main__":
    main()
