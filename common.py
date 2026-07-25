from __future__ import annotations
from datetime import date, datetime
from pathlib import Path
import base64

import streamlit as st
from PIL import Image

APP_NAME = "笹原ほおずき作業管理システム"
APP_SUBTITLE = "HozukiWorks"
APP_ICON = "🟠"  # 画像を表示できない場合の代替表示
APP_VERSION = "Ver2.0.0 Build204"

BASE_DIR = Path(__file__).resolve().parent
APP_ICON_PATH = BASE_DIR / "assets" / "hozuki_icon.png"
APP_LOGO_PATH = BASE_DIR / "assets" / "hozuki_logo.png"

def load_app_icon() -> Image.Image | str:
    """ブラウザタブ用アイコンを返す。画像がなければ絵文字を使用する。"""
    try:
        return Image.open(APP_ICON_PATH)
    except Exception:
        return APP_ICON

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
    st.set_page_config(
        page_title=f"{APP_NAME} {APP_VERSION}",
        page_icon=load_app_icon(),
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    apply_mobile_css()

def apply_mobile_css() -> None:
    st.markdown(
        """
        <style>
        /* Streamlit標準ヘッダー（Deploy・三点メニュー）を全端末で隠す */
        header[data-testid="stHeader"],
        div[data-testid="stToolbar"],
        div[data-testid="stDecoration"],
        div[data-testid="stStatusWidget"] {
            display: none !important;
            height: 0 !important;
        }

        /* 全画面共通 */
        .block-container {
            max-width: 1050px;
            padding-top: 1.1rem;
            padding-bottom: 3rem;
        }
        h1 {
            line-height: 1.25 !important;
            color: #2f6422;
        }
        .hozuki-brand {
            display: flex;
            align-items: center;
            gap: 1.5rem;
            margin: 0.1rem 0 1.7rem 0;
        }
        .hozuki-brand-logo {
            display: block;
            width: 170px;
            height: auto;
            flex: 0 0 auto;
        }
        .hozuki-brand-text {
            min-width: 0;
        }
        .hozuki-brand-title {
            margin: 0;
            color: #2f6422;
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.25;
        }
        .hozuki-brand-subtitle {
            margin-top: 0.35rem;
            color: #6b4a2b;
            font-size: 1rem;
        }
        .hozuki-brand-compact .hozuki-brand-logo {
            width: 118px;
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
            .st-key-desktop_only {
                display: none !important;
            }
            .st-key-mobile_only {
                display: block !important;
            }

            /* Streamlit上部ヘッダーと三点メニューを完全に隠す */
            header[data-testid="stHeader"] {
                display: none !important;
                height: 0 !important;
            }
            div[data-testid="stToolbar"],
            div[data-testid="stDecoration"],
            div[data-testid="stStatusWidget"] {
                display: none !important;
            }
            .block-container {
                padding: 0.9rem 0.75rem 5rem !important;
            }

            /* ブランド表示はスマホでは縦並び・小型化 */
            .hozuki-brand {
                display: flex !important;
                flex-direction: column !important;
                align-items: center !important;
                gap: 0.45rem !important;
                margin: 0 0 1.25rem 0 !important;
                text-align: center !important;
            }
            .hozuki-brand-logo,
            .hozuki-brand-compact .hozuki-brand-logo {
                width: 88px !important;
                max-width: 26vw !important;
                height: auto !important;
            }
            .hozuki-brand-text {
                width: 100% !important;
            }
            .hozuki-brand-title {
                font-size: clamp(1rem, 4.6vw, 1.22rem) !important;
                line-height: 1.2 !important;
                white-space: nowrap !important;
                letter-spacing: -0.02em !important;
            }
            .hozuki-brand-subtitle {
                margin-top: 0.25rem !important;
                font-size: 0.88rem !important;
                white-space: nowrap !important;
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

def _image_data_uri(path: Path) -> str:
    """ロゴ画像をHTML埋め込み用のdata URIに変換する。"""
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except Exception:
        return ""


def show_brand(*, compact: bool = False, show_version: bool = True) -> None:
    """PCとスマホで崩れないレスポンシブなブランド表示。"""
    logo_uri = _image_data_uri(APP_LOGO_PATH) if APP_LOGO_PATH.exists() else ""
    version_html = (
        f'<div class="hozuki-brand-subtitle">{APP_SUBTITLE}　{APP_VERSION}</div>'
        if show_version
        else ""
    )

    if logo_uri:
        compact_class = " hozuki-brand-compact" if compact else ""
        html = f"""
        <div class="hozuki-brand{compact_class}">
            <img class="hozuki-brand-logo" src="{logo_uri}" alt="笹原ほおずきロゴ">
            <div class="hozuki-brand-text">
                <div class="hozuki-brand-title">{APP_NAME}</div>
                {version_html}
            </div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.title(f"{APP_ICON} {APP_NAME}")
        if show_version:
            st.caption(f"{APP_SUBTITLE}　{APP_VERSION}")

def show_header(title: str, subtitle: str = "") -> None:
    st.title(title)
    if subtitle:
        st.caption(subtitle)

def show_sidebar_user(name: str, role: str) -> None:
    if APP_LOGO_PATH.exists():
        st.sidebar.image(str(APP_LOGO_PATH), width=115)
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


def format_short_date(value: object) -> str:
    """募集一覧用の日付を M/D 形式で返す。"""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return f"{value.month}/{value.day}"
    text = normalize_text(value)
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
        return f"{parsed.month}/{parsed.day}"
    except ValueError:
        return text


def format_recruit_no(value: object) -> str:
    text = normalize_text(value)
    return f"No.{text}" if text else "No.-"


def format_recruit_summary(row: dict[str, object]) -> str:
    """募集表示を No.123　7/25　【収穫】　第3畝 の形に統一する。"""
    location = normalize_text(row.get("detail")) or normalize_text(row.get("place"))
    parts = [
        format_recruit_no(row.get("id")),
        format_short_date(row.get("date")),
        f"【{normalize_text(row.get('type'))}】",
    ]
    if location:
        parts.append(location)
    return "　".join(parts)
