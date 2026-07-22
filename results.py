from __future__ import annotations
import streamlit as st
import csvdb
from common import (
    RECRUIT_STATUS_ACCEPTED, RECRUIT_STATUS_ADMIN, RECRUIT_STATUS_ASSIGNED, RECRUIT_STATUS_COMPLETED,
    format_date, normalize_text, require_admin, show_header,
)

def results_screen(*, role: str, mode: str) -> None:
    if not require_admin(role):
        return
    if mode == "create":
        _create()
    elif mode == "list":
        _list()
    elif mode == "edit":
        _edit()
    else:
        st.error("実績画面の指定が不正です。")

def _units(work_type: str) -> list[str]:
    if work_type == "収穫":
        return ["kg"]
    if work_type == "選別（パッキング）":
        return ["パック", "袋"]
    return ["回"]

def _create() -> None:
    show_header("作業実績入力")
    results = csvdb.read("results")
    done_ids = {x.get("recruit_id") for x in results}
    recruits = [
        x for x in csvdb.read("recruit")
        if x.get("status") in {RECRUIT_STATUS_ACCEPTED, RECRUIT_STATUS_ASSIGNED, RECRUIT_STATUS_ADMIN}
        and x.get("id") not in done_ids
    ]
    recruits.sort(key=lambda x: (x.get("date", ""), int(x.get("id") or 0)))

    if not recruits:
        st.info("実績入力できる担当決定済み作業はありません。")
        return

    ids = [x.get("id", "") for x in recruits]
    rid = st.selectbox(
        "対象作業",
        ids,
        format_func=lambda x: next(
            f"{format_date(r.get('date'))}｜{r.get('type')}｜{r.get('member')}"
            for r in recruits if r.get("id") == x
        ),
    )
    row = next(x for x in recruits if x.get("id") == rid)

    with st.form("result_create"):
        value = st.number_input("実績数量", min_value=0.0, step=0.1)
        unit = st.selectbox("単位", _units(row.get("type", "")))
        take_home = (
            st.number_input("持帰り支給量（kg）", min_value=0.0, step=0.1)
            if row.get("type") == "収穫"
            else 0.0
        )
        note = st.text_area("備考")
        submitted = st.form_submit_button("実績を登録", use_container_width=True)

    if not submitted:
        return
    if value <= 0:
        st.error("実績数量は0より大きい値を入力してください。")
        return

    csvdb.append("results", {
        "result_id": csvdb.next_id("results", "result_id"),
        "recruit_id": rid,
        "member_id": row.get("member_id", ""),
        "member_name": row.get("member", ""),
        "work_date": row.get("date", ""),
        "work_type": row.get("type", ""),
        "result_value": value,
        "unit": unit,
        "take_home_qty": take_home if row.get("type") == "収穫" else "",
        "note": note.strip(),
        "previous_recruit_status": row.get("status", ""),
    })

    all_recruits = csvdb.read("recruit")
    for item in all_recruits:
        if item.get("id") == rid:
            item["status"] = RECRUIT_STATUS_COMPLETED
    csvdb.write_all("recruit", all_recruits)

    st.success("実績を登録しました。")
    st.rerun()

def _member_key(row: dict[str, str]) -> str:
    member_id = normalize_text(row.get("member_id"))
    member_name = normalize_text(row.get("member_name"))
    return member_id or f"name:{member_name}"

def _member_label(member_key: str, rows: list[dict[str, str]]) -> str:
    matching = [row for row in rows if _member_key(row) == member_key]
    if not matching:
        return member_key
    name = normalize_text(matching[0].get("member_name")) or "氏名未登録"
    return name


def _result_summary(row: dict[str, str]) -> str:
    return (
        f"{format_date(row.get('work_date'))}｜"
        f"{normalize_text(row.get('work_type'))}｜"
        f"{normalize_text(row.get('member_name'))}"
    )


def _result_detail(row: dict[str, str]) -> None:
    st.write(f"**作業日：** {format_date(row.get('work_date'))}")
    st.write(f"**作業区分：** {normalize_text(row.get('work_type'))}")
    st.write(f"**担当：** {normalize_text(row.get('member_name'))}")
    st.write(f"**実績：** {normalize_text(row.get('result_value'))} {normalize_text(row.get('unit'))}")
    if row.get('take_home_qty') not in {'', None, '0', '0.0'}:
        st.write(f"**持帰り支給量：** {row.get('take_home_qty')} kg")
    if normalize_text(row.get('note')):
        st.caption(f"備考：{normalize_text(row.get('note'))}")


def _result_table(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    data = []
    for row in rows:
        data.append({
            '日付': format_date(row.get('work_date')),
            '作業': normalize_text(row.get('work_type')),
            '担当': normalize_text(row.get('member_name')),
            '実績数量': normalize_text(row.get('result_value')),
            '単位': normalize_text(row.get('unit')),
            '持帰りkg': normalize_text(row.get('take_home_qty')),
            '備考': normalize_text(row.get('note')),
        })
    return data


def _list() -> None:
    show_header('作業実績一覧')
    all_rows = sorted(csvdb.read('results'), key=lambda x:(x.get('work_date',''),int(x.get('result_id') or 0)), reverse=True)
    if not all_rows:
        st.info('実績は登録されていません。'); return
    display_mode=st.radio('表示方法',['全て','メンバー毎'],horizontal=True,key='results_display_mode')
    rows=all_rows; selected_member_label=''
    if display_mode=='メンバー毎':
        member_keys=sorted({_member_key(row) for row in all_rows},key=lambda key:_member_label(key,all_rows))
        selected_member=st.selectbox('表示するメンバー',member_keys,format_func=lambda key:_member_label(key,all_rows),key='results_member_filter')
        selected_member_label=_member_label(selected_member,all_rows)
        rows=[row for row in all_rows if _member_key(row)==selected_member]
    st.caption(f"全 {len(rows)} 件" if display_mode=='全て' else f"{selected_member_label}：{len(rows)} 件")
    with st.container(key='desktop_only'):
        st.dataframe(_result_table(rows),use_container_width=True,hide_index=True)
    with st.container(key='mobile_only'):
        for row in rows:
            with st.expander(_result_summary(row)):
                _result_detail(row)

def _restore_recruit_after_delete(recruit_id: str, previous_status: str = "") -> None:
    recruits = csvdb.read("recruit")
    fallback = previous_status if previous_status in {
        RECRUIT_STATUS_ACCEPTED, RECRUIT_STATUS_ASSIGNED, RECRUIT_STATUS_ADMIN
    } else RECRUIT_STATUS_ACCEPTED
    for item in recruits:
        if item.get("id") == recruit_id and item.get("status") == RECRUIT_STATUS_COMPLETED:
            item["status"] = fallback
            break
    csvdb.write_all("recruit", recruits)


def _delete_result(result_id: str) -> None:
    rows = csvdb.read("results")
    target = next((row for row in rows if row.get("result_id") == result_id), None)
    if target is None:
        st.error("削除対象の実績が見つかりません。")
        return
    remaining = [row for row in rows if row.get("result_id") != result_id]
    csvdb.write_all("results", remaining)
    _restore_recruit_after_delete(
        normalize_text(target.get("recruit_id")),
        normalize_text(target.get("previous_recruit_status")),
    )
    st.session_state["result_delete_message"] = "実績を削除し、対象作業を実績入力前の状態へ戻しました。"
    st.rerun()


def _edit() -> None:
    show_header("作業実績編集・削除")
    message = st.session_state.pop("result_delete_message", "")
    if message:
        st.success(message)

    rows = csvdb.read("results")
    if not rows:
        st.info("実績は登録されていません。")
        return

    rows.sort(key=lambda x: (x.get("work_date", ""), int(x.get("result_id") or 0)), reverse=True)
    ids = [x.get("result_id", "") for x in rows]
    result_id = st.selectbox(
        "編集する実績",
        ids,
        format_func=lambda x: next(
            f"{x}：{r.get('work_date')}｜{r.get('work_type')}｜{r.get('member_name')}"
            for r in rows if r.get("result_id") == x
        ),
        key="result_edit_select",
    )
    row = next(x for x in rows if x.get("result_id") == result_id)

    units = _units(row.get("work_type", ""))
    current_unit = normalize_text(row.get("unit"))
    if current_unit and current_unit not in units:
        units.append(current_unit)
    if not current_unit:
        current_unit = units[0]

    with st.form(f"result_edit_{result_id}"):
        value = st.number_input(
            "実績数量", min_value=0.0,
            value=float(row.get("result_value") or 0), step=0.1,
        )
        unit = st.selectbox("単位", units, index=units.index(current_unit))
        take_home = (
            st.number_input(
                "持帰り支給量（kg）", min_value=0.0,
                value=float(row.get("take_home_qty") or 0), step=0.1,
            )
            if row.get("work_type") == "収穫" else 0.0
        )
        note = st.text_area("備考", value=row.get("note", ""))
        submitted = st.form_submit_button("変更を保存", use_container_width=True)

    if submitted:
        if value <= 0:
            st.error("実績数量は0より大きい値を入力してください。")
        else:
            for item in rows:
                if item.get("result_id") == result_id:
                    item.update({
                        "result_value": value,
                        "unit": unit,
                        "take_home_qty": take_home if row.get("work_type") == "収穫" else "",
                        "note": note.strip(),
                    })
                    break
            csvdb.write_all("results", rows)
            st.success("実績を更新しました。")

    st.divider()
    st.subheader("実績削除")
    st.warning("削除すると、この作業は再び実績入力できる状態に戻ります。")
    confirm = st.checkbox(
        "この実績を削除することを確認しました",
        key=f"delete_result_confirm_{result_id}",
    )
    if st.button(
        "選択した実績を削除",
        type="primary",
        disabled=not confirm,
        use_container_width=True,
        key=f"delete_result_button_{result_id}",
    ):
        _delete_result(result_id)
