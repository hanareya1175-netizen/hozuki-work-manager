from __future__ import annotations
from datetime import date, datetime
import streamlit as st

APP_NAME = "食用ほおずき作業管理システム"
APP_SUBTITLE = "HozukiWorks"
APP_ICON = "assets/app_icon.png"
APP_VERSION = "Ver2.0.0 Build212"

ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
ROLE_LABELS = {ROLE_ADMIN: "管理者", ROLE_MEMBER: "メンバー"}

MEMBER_STATUS_ACTIVE = "有効"
MEMBER_STATUS_INACTIVE = "無効"

RECRUIT_STATUS_OPEN = "募集中"
RECRUIT_STATUS_ACCEPTED = "引受済"
RECRUIT_STATUS_ASSIGNED = "指名済"
RECRUIT_STATUS_ADMIN = "管理者作業"
RECRUIT_STATUS_COMPLETED = "完了"
RECRUIT_STATUS_CANCELLED = "取消"

WORK_TYPES = ["収穫", "選別（パッキング）", "配達", "冷凍処理"]
PLACES = ["A畑", "B畑", "C畑", "選別作業所", "その他"]

def normalize_text(value: object) -> str:
    return "" if value is None else str(value).strip()

def normalize_role(value: object) -> str:
    role = normalize_text(value).lower()
    if role in {"admin", "administrator", "管理者"}:
        return ROLE_ADMIN
    if role in {"member", "user", "メンバー"}:
        return ROLE_MEMBER
    return role

def set_page_config() -> None:
    from pathlib import Path
    from PIL import Image

    icon_path = Path(APP_ICON)
    page_icon = Image.open(icon_path) if icon_path.exists() else "🍊"
    st.set_page_config(
        page_title=f"{APP_NAME} {APP_VERSION}",
        page_icon=page_icon,
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    apply_mobile_css()

def apply_mobile_css() -> None:
    st.markdown(
        """
        <style>
        /* Streamlit Community Cloud の上部ツールバーを全画面で非表示 */
        header[data-testid="stHeader"],
        div[data-testid="stToolbar"],
        div[data-testid="stDecoration"],
        div[data-testid="stStatusWidget"],
        div[data-testid="stAppDeployButton"],
        button[data-testid="stBaseButton-header"],
        #MainMenu,
        footer {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            min-height: 0 !important;
        }

        /* 全画面共通 */
        .block-container {
            max-width: 1050px;
            padding-top: 0.55rem;
            padding-bottom: 3rem;
        }
        h1 {
            line-height: 1.25 !important;
        }
        .hozuki-new-badge {
            color: #8fd400 !important;
            font-weight: 800;
            font-size: 1.05rem;
            line-height: 1;
            margin: 0 0 0.18rem 0.15rem;
        }
        div[data-testid="stButton"] > button,
        div[data-testid="stFormSubmitButton"] > button {
            min-height: 3.15rem;
            font-size: 1.05rem;
            font-weight: 700;
            border-radius: 0.75rem;
        }
        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            min-height: 3rem;
            font-size: 1rem;
        }
        div[role="radiogroup"] label {
            min-height: 2.7rem;
            padding: 0.25rem 0.35rem;
        }
        div[data-testid="stAlert"] {
            border-radius: 0.75rem;
        }


        /* HozukiWorks 共通ヘッダー */
        .hozuki-app-header {
            display: flex;
            align-items: center;
            gap: 2.4rem;
            width: 100%;
            margin: 0.2rem 0 1.3rem 0;
        }
        .hozuki-logo-wrap {
            flex: 0 0 200px;
            width: 200px;
        }
        .hozuki-app-logo {
            display: block;
            width: 200px;
            height: auto;
            max-width: 100%;
        }
        .hozuki-logo-fallback {
            font-size: 5rem;
            line-height: 1;
        }
        .hozuki-header-copy {
            min-width: 0;
            flex: 1 1 auto;
        }
        .hozuki-main-title {
            color: #27320f;
            font-size: clamp(2rem, 3vw, 3.15rem);
            font-weight: 800;
            line-height: 1.18;
            overflow-wrap: anywhere;
        }
        .hozuki-brand-name {
            margin-top: 0.8rem;
            color: #6d4318;
            font-size: 1.2rem;
            font-weight: 600;
            line-height: 1.35;
        }
        .hozuki-version {
            margin-top: 0.18rem;
            color: #6b7280;
            font-size: 1rem;
            line-height: 1.35;
        }

        /* PC・スマホで一覧表示を切り替える */
        .st-key-mobile_only {
            display: none;
        }
        .st-key-desktop_only {
            display: block;
        }
        div[data-testid="stExpander"] details summary {
            padding-top: 0.45rem !important;
            padding-bottom: 0.45rem !important;
        }
        div[data-testid="stExpander"] details summary p {
            font-size: 1rem !important;
            font-weight: 700 !important;
        }
        div[data-testid="stExpanderDetails"] {
            padding-top: 0.25rem !important;
            padding-bottom: 0.55rem !important;
        }

        /* 一覧表示をコンパクトにする */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 0.55rem;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] > div {
            padding: 0.55rem 0.75rem !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] p {
            margin-bottom: 0.15rem !important;
            line-height: 1.35 !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] h3 {
            margin-top: 0 !important;
            margin-bottom: 0.25rem !important;
            line-height: 1.25 !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] .stCaption {
            margin-top: 0 !important;
            margin-bottom: 0 !important;
        }
        hr {
            margin-top: 0.65rem !important;
            margin-bottom: 0.65rem !important;
        }

        /* スマートフォン */
        @media (max-width: 700px) {

            .hozuki-app-header {
                align-items: center;
                gap: 0.5rem;
                margin: 0 0 0.72rem 0;
            }
            .hozuki-logo-wrap {
                flex: 0 0 58px;
                width: 58px;
            }
            .hozuki-app-logo {
                width: 58px;
            }
            .hozuki-logo-fallback {
                font-size: 2.2rem;
            }
            .hozuki-main-title {
                font-size: 0.96rem;
                line-height: 1.15;
                letter-spacing: -0.045em;
                white-space: nowrap;
                overflow-wrap: normal;
            }
            .hozuki-brand-name {
                margin-top: 0.28rem;
                font-size: 0.83rem;
            }
            .hozuki-version {
                margin-top: 0.04rem;
                font-size: 0.74rem;
            }

            .st-key-desktop_only {
                display: none !important;
            }
            .st-key-mobile_only {
                display: block !important;
            }

            .block-container {
                padding: 0.9rem 0.75rem 5rem !important;
            }
            h1 {
                font-size: 1.55rem !important;
                margin-bottom: 0.3rem !important;
            }
            h2 {
                font-size: 1.35rem !important;
            }
            h3 {
                font-size: 1.18rem !important;
                margin-top: 0.25rem !important;
                margin-bottom: 0.45rem !important;
            }
            p, label, .stCaption {
                font-size: 1rem !important;
            }
            div[data-testid="stHorizontalBlock"] {
                gap: 0.45rem;
            }
            div[data-testid="stMetric"] {
                padding: 0.25rem 0;
            }
            div[data-testid="stMetricValue"] {
                font-size: 1.65rem;
            }
            div[data-testid="stButton"] > button,
            div[data-testid="stFormSubmitButton"] > button {
                width: 100%;
                min-height: 3.45rem;
                font-size: 1.12rem;
            }

            /* Reliable NEW badge: rendered as HTML, not a button pseudo-element */
            .hozuki-new-badge {
                display: inline-block !important;
                margin-top: 0.82rem !important;
                padding: 0.18rem 0.38rem !important;
                border-radius: 0.45rem !important;
                background-color: #dfeec8 !important;
                color: #365b24 !important;
                font-size: 0.76rem !important;
                font-weight: 800 !important;
                line-height: 1.15 !important;
                text-align: center !important;
                white-space: nowrap !important;
            }

            /* スマホ募集一覧：左寄せ・太字 */
            [class*="st-key-mobile_detail_"] button,
            [class*="st-key-mobile_detail_"] div[data-testid="stButton"] > button {
                justify-content: flex-start !important;
                text-align: left !important;
                font-weight: 700 !important;
                padding-left: 0.85rem !important;
            }
            /* NEW募集：淡い黄緑の小さなバッジを左端に表示 */
            [class*="st-key-mobile_new_detail_"] div[data-testid="stButton"] > button::before {
                content: "NEW";
                display: inline-block;
                flex: 0 0 auto;
                margin-right: 0.55rem;
                padding: 0.14rem 0.42rem;
                border-radius: 0.45rem;
                background: #dfeec8;
                color: #3f6427;
                font-size: 0.78rem;
                font-weight: 800;
                line-height: 1.15;
                letter-spacing: 0.02em;
            }
            [class*="st-key-mobile_new_detail_"] div[data-testid="stButton"] > button {
                justify-content: flex-start !important;
                text-align: left !important;
                font-weight: 700 !important;
                padding-left: 0.85rem !important;
            }
            [class*="st-key-mobile_new_detail_"] div[data-testid="stButton"] > button p,
            [class*="st-key-mobile_new_detail_"] div[data-testid="stButton"] > button span {
                text-align: left !important;
                font-weight: 700 !important;
            }
            [class*="st-key-mobile_detail_"] button p,
            [class*="st-key-mobile_detail_"] button span,
            [class*="st-key-mobile_detail_"] div[data-testid="stButton"] > button p {
                display: block !important;
                width: 100% !important;
                text-align: left !important;
                font-weight: 700 !important;
            }
            /* メンバー利用を優先し、スマホではサイドバーを完全に隠す */
            section[data-testid="stSidebar"] {
                display: none !important;
            }
            div[data-testid="collapsedControl"],
            button[data-testid="baseButton-headerNoPadding"] {
                display: none !important;
            }
            [data-testid="stAppViewContainer"] > .main {
                margin-left: 0 !important;
                width: 100% !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def show_header(title: str = APP_NAME, subtitle: str = "") -> None:
    """共通ヘッダーを表示する。

    アプリのホーム／ログインでは正式名称を主タイトルとし、
    HozukiWorks とバージョンを別行表示する。各機能画面では
    画面名を主タイトルとして表示する。
    """
    import base64
    from pathlib import Path

    icon_path = Path(APP_ICON)
    icon_html = "<div class='hozuki-logo-fallback'>🍊</div>"
    if icon_path.exists():
        mime = "image/png" if icon_path.suffix.lower() == ".png" else "image/jpeg"
        encoded = base64.b64encode(icon_path.read_bytes()).decode("ascii")
        icon_html = (
            f"<img class='hozuki-app-logo' "
            f"src='data:{mime};base64,{encoded}' alt='HozukiWorks logo'>"
        )

    is_app_header = title == APP_NAME
    if is_app_header:
        detail = subtitle or APP_SUBTITLE
        # 呼出側に旧形式の連結文字列が残っていても、必ず三段に分ける。
        login_label = "ログイン" if "ログイン" in detail else ""
        meta_html = (
            f"<div class='hozuki-brand-name'>{APP_SUBTITLE}</div>"
            f"<div class='hozuki-version'>{APP_VERSION}"
            f"{'　' + login_label if login_label else ''}</div>"
        )
    else:
        meta_html = (
            f"<div class='hozuki-brand-name'>{APP_SUBTITLE}</div>"
            f"<div class='hozuki-version'>{APP_VERSION}</div>"
        )

    st.markdown(
        f"""
        <div class="hozuki-app-header">
          <div class="hozuki-logo-wrap">{icon_html}</div>
          <div class="hozuki-header-copy">
            <div class="hozuki-main-title">{title}</div>
            {meta_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def show_sidebar_user(name: str, role: str) -> None:
    st.sidebar.markdown(f"### {APP_NAME}")
    st.sidebar.write(f"**{name}**")
    st.sidebar.caption(ROLE_LABELS.get(normalize_role(role), role))
    st.sidebar.caption(APP_VERSION)

def require_admin(role: str) -> bool:
    if normalize_role(role) != ROLE_ADMIN:
        st.error("この画面は管理者専用です。")
        return False
    return True

def format_date(value: object) -> str:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%Y/%m/%d")
    text = normalize_text(value)
    try:
        return datetime.strptime(text, "%Y-%m-%d").strftime("%Y/%m/%d")
    except ValueError:
        return text
