from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime
import streamlit as st
import csvdb
from common import require_admin, show_header

COLLECTIONS = ["members", "places", "worktypes", "recruit", "results", "notifications", "notification_batches"]
SEASON_COLLECTIONS = ["recruit", "results", "notifications", "notification_batches"]


def _csv_bytes(rows: list[dict[str,str]]) -> bytes:
    out=io.StringIO(newline="")
    fields=[]
    for row in rows:
        for key in row:
            if key not in fields: fields.append(key)
    if not fields: fields=["id"]
    w=csv.DictWriter(out,fieldnames=fields); w.writeheader(); w.writerows(rows)
    return ("\ufeff"+out.getvalue()).encode("utf-8")


def _backup_zip() -> bytes:
    bio=io.BytesIO()
    with zipfile.ZipFile(bio,"w",zipfile.ZIP_DEFLATED) as z:
        for name in COLLECTIONS: z.writestr(f"{name}.csv",_csv_bytes(csvdb.read(name)))
    return bio.getvalue()


def data_admin_screen(*, role: str) -> None:
    if not require_admin(role): return
    show_header("データ管理")
    st.info(f"現在の保存先：{csvdb.storage_label()}")
    stamp=datetime.now().strftime("%Y%m%d_%H%M")
    st.download_button("全データをバックアップ",data=_backup_zip(),file_name=f"HozukiWorks_backup_{stamp}.zip",mime="application/zip",use_container_width=True)
    st.download_button("実績をExcel用CSVで出力",data=_csv_bytes(csvdb.read("results")),file_name=f"HozukiWorks_results_{stamp}.csv",mime="text/csv",use_container_width=True)
    st.divider(); st.subheader("年度データのリセット")
    st.warning("募集・実績・通知だけを削除します。メンバー、圃場、作業区分は残ります。先にバックアップしてください。")
    confirm=st.checkbox("バックアップ済みであることを確認しました")
    if st.button("年度データをリセット",disabled=not confirm,use_container_width=True):
        for name in SEASON_COLLECTIONS: csvdb.write_all(name,[])
        st.success("年度データをリセットしました。"); st.rerun()
