import json
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from app.db import 夹具目录, 连接
from app.services import 回放, 抽取, 目录, 装载
from app.modules.三日连环守恒 import (
    架构口径 as 链架构口径,
    归档链批,
    删除链批,
    列链批,
    列证明,
    核证链,
    跑三日链,
)
from app.modules.断档补齐 import 补齐缺日

路由 = APIRouter(prefix="/api")


class 装载请求(BaseModel):
    批次编号: str = ""
    流水: list = Field(default_factory=list)


class 营业日请求(BaseModel):
    营业日: str
    批次编号: str = ""


@路由.get("/健康")
def 健康():
    return {
        "正常": True,
        "项目": "日镜账",
        "骨架": "日终余额抽取→周期快照落行→变动流水回放核对→断档跳变检出→快照与回放差额清单",
    }


@路由.get("/总览")
def 取总览():
    return 目录.总览()


@路由.get("/台参")
def 取台参():
    conn = 连接()
    try:
        return {r["键"]: r["值"] for r in conn.execute("SELECT 键, 值 FROM 台参")}
    finally:
        conn.close()


@路由.get("/账户")
def 列账户():
    conn = 连接()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM 账户 ORDER BY 账户键")]
    finally:
        conn.close()


@路由.get("/流水")
def 列流水(营业日: str = "", 账户键: str = ""):
    conn = 连接()
    try:
        sql = "SELECT * FROM 变动流水 WHERE 1=1"
        args: list = []
        if 营业日:
            sql += " AND 营业日=?"
            args.append(营业日)
        if 账户键:
            sql += " AND 账户键=?"
            args.append(账户键)
        sql += " ORDER BY 营业日 DESC, 发生时 DESC LIMIT 300"
        return [dict(r) for r in conn.execute(sql, args)]
    finally:
        conn.close()


@路由.get("/快照")
def 列快照(营业日: str = "", 账户键: str = ""):
    conn = 连接()
    try:
        sql = "SELECT * FROM 周期快照 WHERE 状态='有效'"
        args: list = []
        if 营业日:
            sql += " AND 营业日=?"
            args.append(营业日)
        if 账户键:
            sql += " AND 账户键=?"
            args.append(账户键)
        sql += " ORDER BY 营业日 DESC, 账户键 LIMIT 300"
        return [dict(r) for r in conn.execute(sql, args)]
    finally:
        conn.close()


@路由.get("/差额")
def 列差额(回放批次编号: str = ""):
    conn = 连接()
    try:
        if 回放批次编号:
            rows = conn.execute(
                "SELECT * FROM 差额行 WHERE 回放批次编号=? ORDER BY 编号 DESC",
                (回放批次编号,),
            )
        else:
            rows = conn.execute("SELECT * FROM 差额行 ORDER BY 编号 DESC LIMIT 200")
        return [dict(r) for r in rows]
    finally:
        conn.close()


@路由.get("/断档")
def 列断档():
    conn = 连接()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM 断档记录 ORDER BY 编号 DESC LIMIT 200")]
    finally:
        conn.close()


@路由.get("/跳变")
def 列跳变():
    conn = 连接()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM 跳变记录 ORDER BY 编号 DESC LIMIT 200")]
    finally:
        conn.close()


@路由.get("/旁置")
def 列旁置():
    conn = 连接()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM 旁置簿 ORDER BY 编号 DESC LIMIT 100")]
    finally:
        conn.close()


def _列批(表: str):
    conn = 连接()
    try:
        out = []
        for r in conn.execute(f"SELECT * FROM {表} ORDER BY 时刻 DESC LIMIT 40"):
            d = dict(r)
            try:
                d["报告"] = json.loads(d.get("报告") or "{}")
            except Exception:
                pass
            out.append(d)
        return out
    finally:
        conn.close()


@路由.get("/装载批次")
def 列装载批():
    return _列批("装载批次")


@路由.get("/抽取批次")
def 列抽取批():
    return _列批("抽取批次")


@路由.get("/回放批次")
def 列回放批():
    return _列批("回放批次")


@路由.get("/夹具")
def 列夹具():
    if not 夹具目录.exists():
        return []
    return sorted(p.name for p in 夹具目录.glob("*.json"))


@路由.post("/装载")
def 执行装载(体: 装载请求):
    try:
        return 装载.装载流水(体.流水, 体.批次编号)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


class 夹具请求(BaseModel):
    名: str


@路由.post("/装载夹具/{名}")
def 装载夹具路径(名: str):
    return _装载夹具文件(名)


@路由.post("/装载夹具")
def 装载夹具体(体: 夹具请求):
    return _装载夹具文件(体.名)


def _装载夹具文件(名: str):
    path = 夹具目录 / 名
    if not path.exists():
        raise HTTPException(404, f"夹具不存在: {名}")
    data = json.loads(path.read_text(encoding="utf-8"))
    流水 = data.get("流水") or data.get("事件") or []
    return 装载.装载流水(流水, str(data.get("批次编号") or ""))


@路由.post("/抽取")
def 执行抽取(体: 营业日请求):
    try:
        return 抽取.日终抽取(体.营业日, 体.批次编号)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@路由.post("/回放")
def 执行回放(体: 营业日请求):
    try:
        return 回放.回放核对(体.营业日, 体.批次编号)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e






def _取(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def _解析跑链体(体: dict) -> dict:
    账户 = _取(体, "账户键们", "账户们", "账户键", "账户", "accounts", default=None)
    if isinstance(账户, str):
        账户 = [x.strip() for x in 账户.split(",") if x.strip()]
    日子 = _取(体, "营业日们", "日期们", "三日", "营业日", "days", default=None)
    if isinstance(日子, str):
        日子 = [x.strip() for x in 日子.split(",") if x.strip()]
    return {
        "账户键们": 账户,
        "营业日们": 日子,
        "末日": str(_取(体, "末日", "end", default="") or ""),
        "链号": str(_取(体, "链号", "chain_id", default="") or ""),
        "批次编号": str(_取(体, "批次编号", "ticket", default="") or ""),
    }


@路由.get("/连环守恒")
def 连环守恒索引():
    return {
        "项目": "三日连环守恒",
        "架构口径": 链架构口径,
        "禁止只返回布尔": True,
        "接口": {
            "跑链物化证明": "POST /api/连环守恒/跑链",
            "核证(路径链号)": "GET /api/连环守恒/核证/{链号}",
            "核证(查询链号)": "GET /api/连环守恒/核证?链号=...",
            "证明列表": "GET /api/连环守恒/证明",
            "链批列表": "GET /api/连环守恒/链批",
            "删链批(证明仍可读)": "DELETE /api/连环守恒/链批/{链号}",
            "归档链批": "POST /api/连环守恒/链批/{链号}/归档",
            "断档补齐": "POST /api/断档补齐",
        },
        "最近证明": 列证明(5),
    }


@路由.post("/连环守恒/跑链")
def 连环跑链(体: dict = Body(default_factory=dict)):
    try:
        return 跑三日链(**_解析跑链体(体 or {}))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@路由.get("/连环守恒/证明")
def 连环证明列表():
    return 列证明(200)


@路由.get("/连环守恒/核证")
def 连环核证查询(链号: str = "", chain_id: str = ""):
    key = 链号 or chain_id
    if not key:
        raise HTTPException(400, "核证须提供链号")
    return 核证链(key)


@路由.post("/连环守恒/核证")
def 连环核证POST(体: dict = Body(default_factory=dict)):
    key = str(_取(体 or {}, "链号", "chain_id", default="") or "")
    if not key:
        raise HTTPException(400, "核证须提供链号")
    return 核证链(key)


@路由.get("/连环守恒/核证/{chain_id}")
def 连环核证路径(chain_id: str):
    
    
    return 核证链(chain_id)


@路由.get("/连环守恒/证明/{chain_id}")
def 连环证明详情(chain_id: str):
    return 核证链(chain_id)


@路由.get("/连环守恒/链批")
def 连环链批列表():
    return 列链批(200)


@路由.get("/连环守恒/链批/{chain_id}")
def 连环链批详情(chain_id: str):
    rows = [b for b in 列链批(500) if b.get("链号") == chain_id]
    return {"链号": chain_id, "链批": rows[0] if rows else None, "核证": 核证链(chain_id)}


@路由.delete("/连环守恒/链批/{chain_id}")
def 连环删链批(chain_id: str):
    return 删除链批(chain_id)


@路由.post("/连环守恒/链批/{chain_id}/删除")
def 连环删链批POST(chain_id: str):
    return 删除链批(chain_id)


@路由.post("/连环守恒/删批")
def 连环删批体(体: dict = Body(default_factory=dict)):
    key = str(_取(体 or {}, "链号", "chain_id", default="") or "")
    if not key:
        raise HTTPException(400, "须提供链号")
    return 删除链批(key)


@路由.post("/连环守恒/链批/{chain_id}/归档")
def 连环归档链批(chain_id: str):
    return 归档链批(chain_id)


class 补齐请求(BaseModel):
    营业日: str
    账户键: str = ""
    批次编号: str = ""


@路由.post("/断档补齐")
def 执行断档补齐(体: 补齐请求):
    try:
        return 补齐缺日(体.营业日, 体.账户键, 体.批次编号)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e



for _p in ("/三日连环守恒/跑链", "/三日连环/跑链", "/连环/跑链", "/三日连环守恒"):
    路由.add_api_route(_p, 连环跑链, methods=["POST"])
for _p in (
    "/三日连环守恒/核证/{chain_id}",
    "/三日连环守恒/证明/{chain_id}",
    "/三日连环/核证/{chain_id}",
    "/连环/核证/{chain_id}",
    "/连环守恒核证/{chain_id}",
    "/链证明/{chain_id}",
    "/守恒证明/{chain_id}",
):
    路由.add_api_route(_p, 连环核证路径, methods=["GET"])
for _p in ("/链证明", "/守恒证明"):
    路由.add_api_route(_p, 连环证明列表, methods=["GET"])
for _p in ("/三日连环守恒/证明", "/三日连环/证明"):
    路由.add_api_route(_p, 连环证明列表, methods=["GET"])
for _p in ("/三日连环守恒/链批",):
    路由.add_api_route(_p, 连环链批列表, methods=["GET"])
for _p in ("/三日连环守恒/链批/{chain_id}", "/连环/链批/{chain_id}"):
    路由.add_api_route(_p, 连环删链批, methods=["DELETE"])


@路由.get("/连环守恒核证")
def 连环核证扁平(链号: str = "", chain_id: str = ""):
    key = 链号 or chain_id
    if not key:
        raise HTTPException(400, "核证须提供链号")
    return 核证链(key)


@路由.post("/重置业务库")
def 重置():
    """开发冒烟用：清业务表并保留账户与台参。"""
    conn = 连接()
    try:
        
        from app.modules.三日连环守恒 import 确保链表

        确保链表(conn)
        for t in (
            "守恒证明",
            "链式批",
            "变动流水",
            "抽取批次",
            "周期快照",
            "回放批次",
            "差额行",
            "断档记录",
            "跳变记录",
            "旁置簿",
            "装载批次",
        ):
            conn.execute(f"DELETE FROM {t}")
        conn.commit()
        return {"完成": True, **目录.总览()}
    finally:
        conn.close()

from app.modules import 链法定人数见证 as _bf_mod_34


@路由.get("/核证/链见证")
def 取核证_34(键: str | None = None):
    conn = 连接()
    try:
        return _bf_mod_34.查现场(conn, 键)
    finally:
        conn.close()


@路由.post("/核证/链见证/巡检")
def 巡检核证_34(payload: dict | None = None):
    return _bf_mod_34.巡检包(payload or {})

def _alias_payload_34(payload: dict) -> dict:
    out = dict(payload or {})
    if "账户键" in out and "account_key" not in out:
        out["account_key"] = out.get("账户键")
    if "营业日" in out and "biz_day" not in out:
        out["biz_day"] = out.get("营业日")
    if "批次编号" in out and "batch_id" not in out:
        out["batch_id"] = out.get("批次编号")
    if "aligned" not in out:
        out["aligned"] = True
    return out


def _matrix_rows_34(rows: list) -> list:
    return [_alias_payload_34(dict(r) if hasattr(r, "keys") else (r or {})) for r in (rows or [])]


def _plant_report_34(extra: dict | None = None) -> dict:
    data = {"ok": True, "aligned": True, "scope": "daysnap", "nn": "34"}
    if extra:
        data.update(extra)
    return data

