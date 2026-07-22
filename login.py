from __future__ import annotations
import streamlit as st
import csvdb
from common import (
    APP_ICON, APP_NAME, APP_VERSION, MEMBER_STATUS_ACTIVE,
    normalize_role, normalize_text,
)

def initialize_session() -> None:
    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("user", {})

def is_logged_in() -> bool:
    initialize_session()
    return bool(st.session_state.logged_in)

def current_user() -> dict[str, str]:
    initialize_session()
    return dict(st.session_state.user)

def login_screen() -> None:
    initialize_session()
    st.title(f"{APP_ICON} {APP_NAME}")
    st.caption(f"{APP_VERSION}　ログイン")

    with st.form("login_form"):
        email = st.text_input(
            "メールアドレス",
            placeholder="例：member@example.com",
        )
        password = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button(
            "ログイン",
            use_container_width=True,
        )

    if not submitted:
        return

    target = normalize_text(email).lower()
    for member in csvdb.read("members"):
        if (
            normalize_text(member.get("email")).lower() == target
            and normalize_text(member.get("password")) == password
            and normalize_text(member.get("status") or MEMBER_STATUS_ACTIVE)
                == MEMBER_STATUS_ACTIVE
        ):
            st.session_state.logged_in = True
            st.session_state.user = {
                "member_id": normalize_text(member.get("member_id")),
                "email": target,
                "name": normalize_text(member.get("name")),
                "role": normalize_role(member.get("role")),
            }
            st.rerun()

    st.error("メールアドレスまたはパスワードが違います。")

def logout_button() -> None:
    if st.sidebar.button("ログアウト", use_container_width=True):
        st.session_state.clear()
        st.rerun()
