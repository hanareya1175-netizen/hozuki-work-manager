from __future__ import annotations
import re
import streamlit as st
import csvdb
from common import (
    MEMBER_STATUS_ACTIVE, MEMBER_STATUS_INACTIVE, ROLE_ADMIN, ROLE_MEMBER,
    ROLE_LABELS, normalize_role, normalize_text, require_admin, show_header,
)

def _valid_email(email: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email))

def members_screen(*, role: str, mode: str, embedded: bool = False) -> None:
    if not require_admin(role): return
    if mode=='create': _create(embedded=embedded)
    elif mode=='list': _list(embedded=embedded)
    elif mode=='edit': _edit(embedded=embedded)
    else: st.error('会員画面の指定が不正です。')

def _create(*, embedded: bool = False) -> None:
    if not embedded:
        show_header('会員登録')
    with st.form('member_create',clear_on_submit=True):
        name=st.text_input('氏名'); email=st.text_input('メールアドレス'); phone=st.text_input('電話番号')
        role=st.selectbox('権限',[ROLE_MEMBER,ROLE_ADMIN],format_func=lambda x:ROLE_LABELS[x])
        password=st.text_input('仮パスワード',type='password')
        submitted=st.form_submit_button('登録',use_container_width=True)
    if not submitted:return
    email=normalize_text(email).lower()
    if not name.strip() or not _valid_email(email) or len(password)<4:
        st.error('氏名、正しいメールアドレス、4文字以上のパスワードを入力してください。'); return
    if any(normalize_text(x.get('email')).lower()==email for x in csvdb.read('members')):
        st.error('同じメールアドレスが登録されています。'); return
    csvdb.append('members',{'member_id':csvdb.next_id('members','member_id'),'email':email,'password':password,'name':name.strip(),'role':role,'status':MEMBER_STATUS_ACTIVE,'phone':phone.strip()})
    st.success('会員を登録しました。')

def _list(*, embedded: bool = False) -> None:
    if not embedded:
        show_header('会員一覧')
    else:
        st.subheader('会員一覧')
    rows=csvdb.read('members')
    if not rows: st.info('会員は登録されていません。'); return
    table=[]
    for r in rows:
        table.append({'ID':normalize_text(r.get('member_id')),'氏名':normalize_text(r.get('name')),'メール':normalize_text(r.get('email')),'電話':normalize_text(r.get('phone')) or '未登録','権限':ROLE_LABELS.get(normalize_role(r.get('role')),r.get('role')),'状態':normalize_text(r.get('status'))})
    with st.container(key='desktop_only'):
        st.dataframe(table,use_container_width=True,hide_index=True)
    with st.container(key='mobile_only'):
        for r in rows:
            label=f"{normalize_text(r.get('name'))}｜{ROLE_LABELS.get(normalize_role(r.get('role')),r.get('role'))}｜{normalize_text(r.get('status'))}"
            with st.expander(label):
                st.write(f"**会員ID：** {normalize_text(r.get('member_id'))}")
                st.write(f"**メール：** {normalize_text(r.get('email'))}")
                st.write(f"**電話：** {normalize_text(r.get('phone')) or '未登録'}")
                st.write(f"**権限：** {ROLE_LABELS.get(normalize_role(r.get('role')),r.get('role'))}")
                st.write(f"**状態：** {normalize_text(r.get('status'))}")

def _edit(*, embedded: bool = False) -> None:
    if not embedded:
        show_header('会員編集')
    rows=csvdb.read('members')
    if not rows: st.info('会員は登録されていません。'); return
    ids=[normalize_text(x.get('member_id')) for x in rows]
    selected=st.selectbox('編集する会員',ids,format_func=lambda mid:next(f"{mid}：{x.get('name')}" for x in rows if normalize_text(x.get('member_id'))==mid))
    row=next(x for x in rows if normalize_text(x.get('member_id'))==selected)
    with st.form('member_edit'):
        name=st.text_input('氏名',value=normalize_text(row.get('name'))); email=st.text_input('メールアドレス',value=normalize_text(row.get('email'))); phone=st.text_input('電話番号',value=normalize_text(row.get('phone')))
        role=st.selectbox('権限',[ROLE_MEMBER,ROLE_ADMIN],index=0 if normalize_role(row.get('role'))==ROLE_MEMBER else 1,format_func=lambda x:ROLE_LABELS[x])
        status=st.selectbox('状態',[MEMBER_STATUS_ACTIVE,MEMBER_STATUS_INACTIVE],index=0 if normalize_text(row.get('status'))!=MEMBER_STATUS_INACTIVE else 1)
        password=st.text_input('新しいパスワード（変更時のみ）',type='password')
        submitted=st.form_submit_button('保存',use_container_width=True)
    if not submitted:return
    email=normalize_text(email).lower()
    if not name.strip() or not _valid_email(email): st.error('氏名と正しいメールアドレスを入力してください。'); return
    for item in rows:
        if normalize_text(item.get('member_id'))==selected:
            item.update({'name':name.strip(),'email':email,'phone':phone.strip(),'role':role,'status':status})
            if password:item['password']=password
            break
    csvdb.write_all('members',rows); st.success('会員情報を更新しました。')
