from __future__ import annotations

import csvdb

ACTIVE = "使用中"
INACTIVE = "使用停止"
DEFAULT_PLACES = ["A畑", "B畑", "C畑", "選別作業所", "その他"]
DEFAULT_WORKTYPES = ["収穫", "選別（パッキング）", "配達", "冷凍処理"]


def _defaults(kind: str) -> list[str]:
    if kind == "places": return DEFAULT_PLACES
    if kind == "worktypes": return DEFAULT_WORKTYPES
    raise ValueError("未対応のマスター種別です。")


def _normalize_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized=[]
    for index,row in enumerate(rows,start=1):
        name=str(row.get("name","")).strip()
        if not name: continue
        status=str(row.get("status",ACTIVE)).strip() or ACTIVE
        try: order=int(str(row.get("sort_order",index)).strip() or index)
        except ValueError: order=index
        normalized.append({"id":str(row.get("id",index)).strip() or str(index),"name":name,"status":status if status in {ACTIVE,INACTIVE} else ACTIVE,"sort_order":str(order)})
    normalized.sort(key=lambda x:(int(x["sort_order"]),int(x["id"]) if x["id"].isdigit() else 999999,x["name"]))
    return normalized


def read_master(kind: str) -> list[dict[str, str]]:
    rows=_normalize_rows(csvdb.read(kind))
    if rows: return rows
    rows=[{"id":str(i),"name":name,"status":ACTIVE,"sort_order":str(i)} for i,name in enumerate(_defaults(kind),start=1)]
    write_master(kind,rows)
    return rows


def write_master(kind: str, rows: list[dict[str, str]]) -> None:
    csvdb.write_all(kind,_normalize_rows(rows))


def active_names(kind: str) -> list[str]:
    return [r["name"] for r in read_master(kind) if r["status"]==ACTIVE]


def next_id(rows: list[dict[str,str]]) -> str:
    vals=[int(r.get("id","0")) for r in rows if str(r.get("id","")).isdigit()]
    return str(max(vals,default=0)+1)


def add_master(kind: str, name: str) -> tuple[bool,str]:
    clean=name.strip()
    if not clean: return False,"名称を入力してください。"
    rows=read_master(kind)
    if any(r["name"]==clean for r in rows): return False,"同じ名称がすでに登録されています。"
    order=max((int(r["sort_order"]) for r in rows),default=0)+1
    rows.append({"id":next_id(rows),"name":clean,"status":ACTIVE,"sort_order":str(order)})
    write_master(kind,rows); return True,"登録しました。"


def update_master(kind: str,item_id: str,name: str,status: str,sort_order: int) -> tuple[bool,str]:
    clean=name.strip()
    if not clean: return False,"名称を入力してください。"
    rows=read_master(kind)
    if any(r["id"]!=item_id and r["name"]==clean for r in rows): return False,"同じ名称がすでに登録されています。"
    target=next((r for r in rows if r["id"]==item_id),None)
    if target is None: return False,"対象データが見つかりません。"
    target.update({"name":clean,"status":status,"sort_order":str(max(1,int(sort_order)))})
    write_master(kind,rows); return True,"変更を保存しました。"
