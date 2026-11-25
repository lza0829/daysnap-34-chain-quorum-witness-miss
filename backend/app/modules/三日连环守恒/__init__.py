"""三日连环守恒 —— 选定账户 × 三个营业日的链式守恒核证，并物化链证明。

架构口径（关键设计取舍，全局只贯彻这一种）
==========================================

**A · 以守恒证明表为准。** 每次跑链在同一个 SQLite 事务里写两行：

1. ``守恒证明`` —— 独立证明表，链号为主键，携带通过否、源指纹、逐户链环明细；
   这是链结论的唯一权威出处，生命周期独立于链式批行。
2. ``链式批`` —— 链式跑批/归档/删除的批行，报告里也嵌一份指纹（仅为方便，
   不是权威）。

因此 **归档/删除 ``链式批`` 行之后，仍可按链号从 ``守恒证明`` 读到完整证明**，
核证接口照常返回 ``valid``。这正是与口径 B（结论只活在链式批报告嵌指纹里、
无独立证明表，删批即不可还原）的可区分点；测试
``test_口径A_删链式批行后证明仍可按链号核证`` 钉死该口径，口径 B 下该断言必失败。

失败闭 / 不得假通过
--------------------

- 三个链日的有效快照缺一即败（删中日快照 → 报「缺中日快照」，整链不通过，
  多户时任一户缺日整链不成功），但仍物化一张「不通过」证明，禁止只回布尔。
- 指纹覆盖作用域内全部快照行（含抽取批次票）、流水行、断档处置行与源纪元。
- 跑链采用「先采指纹 → 交错窗口 → ``BEGIN IMMEDIATE`` 提交前复采比对」的
  乐观守卫：中日被重抽 / 断档补齐一旦在读取后改动源，前后指纹不一致即判
  ``交错冲突``、失败闭落证明，绝不用旧指纹报通过。
- 核证时按链号落库指纹对当前源重新比对：指纹过期则顶层 ``通过=false``、
  ``valid=false``（另保留 ``原始通过`` 历史结论），不得以过期指纹报通过。

同票
----
链号同时作为本次链式批的批次编号；明细 ``同票`` 记录每个快照的抽取批次票、
流水装载票、三日回放批次票，使链证明与三日快照/流水/回放同源同票。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import Any, Callable, Optional

from app.db import 连接
from app.services.时间 import 此刻, 标准化营业日

启用 = True


架构口径 = "A-守恒证明表为准"

_口径说明 = (
    "以独立『守恒证明』表为权威：链结论独立落表，"
    "归档/删除『链式批』行后仍可按链号读证明并核证 valid；"
    "非口径 B（结论仅嵌于链式批报告，删批不可还原）。"
)


链表DDL = """
CREATE TABLE IF NOT EXISTS 守恒证明 (
  链号 TEXT PRIMARY KEY,
  编号 TEXT NOT NULL DEFAULT '',
  架构口径 TEXT NOT NULL,
  营业日们 TEXT NOT NULL DEFAULT '[]',
  期初锚日 TEXT NOT NULL DEFAULT '',
  账户们 TEXT NOT NULL DEFAULT '[]',
  通过 INTEGER NOT NULL DEFAULT 0,
  valid INTEGER NOT NULL DEFAULT 0,
  指纹 TEXT NOT NULL DEFAULT '',
  初指纹 TEXT NOT NULL DEFAULT '',
  提交指纹 TEXT NOT NULL DEFAULT '',
  交错冲突 INTEGER NOT NULL DEFAULT 0,
  明细 TEXT NOT NULL DEFAULT '{}',
  时刻 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 链式批 (
  链号 TEXT PRIMARY KEY,
  编号 TEXT NOT NULL DEFAULT '',
  营业日们 TEXT NOT NULL DEFAULT '[]',
  账户们 TEXT NOT NULL DEFAULT '[]',
  状态 TEXT NOT NULL DEFAULT '在',
  时刻 TEXT NOT NULL,
  报告 TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS 链源纪元 (
  键 TEXT PRIMARY KEY,
  值 INTEGER NOT NULL DEFAULT 0
);
"""



_证明别名 = [
    "连环守恒证明",
    "链证明",
    "连环证明",
    "三日连环证明",
    "三日连环守恒证明",
    "三日连环守恒",
    "三日连环链证",
    "chain_proof",
]
_批别名 = [
    "连环链式批",
    "链批次",
    "连环批次",
    "三日连环批次",
    "三日连环批",
    "chain_batch",
]


def _别名DDL() -> str:
    parts: list[str] = []
    for name in _证明别名:
        parts.append(f"CREATE VIEW IF NOT EXISTS {name} AS SELECT * FROM 守恒证明;")
    for name in _批别名:
        parts.append(f"CREATE VIEW IF NOT EXISTS {name} AS SELECT * FROM 链式批;")
        parts.append(
            f"CREATE TRIGGER IF NOT EXISTS {name}_删 INSTEAD OF DELETE ON {name} "
            f"BEGIN DELETE FROM 链式批 WHERE 链号 = OLD.链号; END;"
        )
    return "\n".join(parts)


def 确保链表(conn) -> None:
    """幂等建表/视图。独立调用（如单测直注服务）时也能自给自足。"""
    conn.executescript(链表DDL)
    conn.executescript(_别名DDL())


def 说明() -> str:
    return "三日连环守恒：选定账户三日链 期初+净额 对 期末，物化独立守恒证明，支持链号核证与删批后回看"






def 推进源纪元(conn) -> int:
    """在抽取/补齐同一事务内调用：推进全局源纪元并返回新值。

    放在专用内部表 ``链源纪元``（不进台参/台面），保证「只要重抽过就换纪元」，
    即使重抽用了同批次号且余额未变，链指纹也必然过期。
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS 链源纪元 (键 TEXT PRIMARY KEY, 值 INTEGER NOT NULL DEFAULT 0)"
    )
    row = conn.execute("SELECT 值 FROM 链源纪元 WHERE 键='全局'").fetchone()
    n = int(row["值"]) + 1 if row and row["值"] is not None else 1
    if row is None:
        conn.execute("INSERT INTO 链源纪元(键, 值) VALUES ('全局', ?)", (n,))
    else:
        conn.execute("UPDATE 链源纪元 SET 值=? WHERE 键='全局'", (n,))
    return n


def _源纪元(conn) -> int:
    try:
        row = conn.execute("SELECT 值 FROM 链源纪元 WHERE 键='全局'").fetchone()
        return int(row["值"]) if row and row["值"] is not None else 0
    except Exception:
        return 0


def _前日(营业日: str) -> str:
    from datetime import date, timedelta

    y, m, d = map(int, 营业日.split("-"))
    return (date(y, m, d) - timedelta(days=1)).isoformat()


def _解析三日(营业日们: Optional[list], 末日: str = "", 营业日: str = "") -> list[str]:
    if 营业日们:
        days = [标准化营业日(str(x)) for x in 营业日们 if str(x).strip()]
        if len(days) == 3:
            return days
        if len(days) == 1:
            
            d2 = days[0]
            return [_前日(_前日(d2)), _前日(d2), d2]
        raise ValueError("三日连环守恒须给出三个营业日（营业日们 长度=3；单个日期视作末日并前推两日）")
    end = (末日 or 营业日 or "").strip()
    if end:
        d2 = 标准化营业日(end)
        return [_前日(_前日(d2)), _前日(d2), d2]
    
    conn = 连接()
    try:
        r = conn.execute("SELECT MAX(营业日) AS d FROM 周期快照").fetchone()
    finally:
        conn.close()
    if not r or not r["d"]:
        raise ValueError("未提供营业日们/末日，且库中无快照可推断三日区间")
    d2 = 标准化营业日(r["d"])
    return [_前日(_前日(d2)), _前日(d2), d2]


def _选定账户(conn, 账户键们: Optional[list]) -> list[str]:
    if 账户键们:
        keys: list[str] = []
        for x in 账户键们:
            k = str(x or "").strip()
            if k and k not in keys:
                keys.append(k)
        if not keys:
            raise ValueError("账户键们 为空")
        ph = ",".join("?" * len(keys))
        rows = conn.execute(
            f"SELECT 账户键 FROM 账户 WHERE 账户键 IN ({ph})", keys
        ).fetchall()
        存在 = {r["账户键"] for r in rows}
        未知 = [k for k in keys if k not in 存在]
        if 未知:
            raise ValueError(f"未知账户: {','.join(未知)}")
        return keys
    return [
        r["账户键"]
        for r in conn.execute(
            "SELECT 账户键 FROM 账户 WHERE 状态='正常' ORDER BY 账户键"
        ).fetchall()
    ]






def _采集源(conn, accounts: list[str], days: list[str]) -> tuple[dict[str, Any], str]:
    anchor = _前日(days[0])
    snap_days = sorted(set(days + [anchor]))
    ph_a = ",".join("?" * len(accounts))
    ph_sd = ",".join("?" * len(snap_days))
    ph_d = ",".join("?" * len(days))

    snaps = [
        dict(r)
        for r in conn.execute(
            f"SELECT 快照键,账户键,营业日,余额,抽取批次编号,来源,状态 "
            f"FROM 周期快照 WHERE 账户键 IN ({ph_a}) AND 营业日 IN ({ph_sd}) "
            f"ORDER BY 快照键",
            [*accounts, *snap_days],
        ).fetchall()
    ]
    flows = [
        dict(r)
        for r in conn.execute(
            f"SELECT 流水号,账户键,营业日,变动额,命运,批次编号 "
            f"FROM 变动流水 WHERE 账户键 IN ({ph_a}) AND 营业日 IN ({ph_d}) "
            f"ORDER BY 流水号",
            [*accounts, *days],
        ).fetchall()
    ]
    gap_days = [anchor, days[0], days[1]]
    ph_gd = ",".join("?" * len(gap_days))
    gaps = [
        dict(r)
        for r in conn.execute(
            f"SELECT 编号,账户键,缺营业日,处置,检出批次编号 "
            f"FROM 断档记录 WHERE 账户键 IN ({ph_a}) AND 缺营业日 IN ({ph_gd}) "
            f"ORDER BY 编号",
            [*accounts, *gap_days],
        ).fetchall()
    ]
    source = {
        "v": 1,
        "源纪元": _源纪元(conn),
        "账户们": accounts,
        "营业日们": days,
        "期初锚日": anchor,
        "快照": snaps,
        "流水": flows,
        "断档": gaps,
    }
    raw = json.dumps(
        source, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    fp = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return source, fp






_位置 = ["首日", "中日", "末日"]


def _build_detail(conn, accounts: list[str], days: list[str], source: dict[str, Any]) -> dict[str, Any]:
    anchor = source["期初锚日"]
    参 = {r["键"]: r["值"] for r in conn.execute("SELECT 键, 值 FROM 台参").fetchall()}
    缺前日策略 = 参.get("缺前日策略", "以零为开端")

    户行 = {
        r["账户键"]: dict(r)
        for r in conn.execute(
            f"SELECT * FROM 账户 WHERE 账户键 IN ({','.join('?' * len(accounts))})",
            accounts,
        ).fetchall()
    }
    快照idx = {(s["账户键"], s["营业日"]): s for s in source["快照"]}
    流水 = source["流水"]

    
    回放票: dict[str, list] = {d: [] for d in days}
    try:
        ph_d = ",".join("?" * len(days))
        for r in conn.execute(
            f"SELECT 编号,营业日,时刻,报告 FROM 回放批次 "
            f"WHERE 营业日 IN ({ph_d}) ORDER BY 时刻 DESC",
            days,
        ).fetchall():
            d = dict(r)
            try:
                rep = json.loads(d.get("报告") or "{}")
            except Exception:
                rep = {}
            回放票.setdefault(d["营业日"], []).append(
                {"回放批次编号": d["编号"], "时刻": d["时刻"], "通过": rep.get("通过"),
                 "差额": rep.get("差额"), "无快照": rep.get("无快照")}
            )
    except Exception:  
        pass

    账户明细: list[dict[str, Any]] = []
    for k in accounts:
        户 = 户行.get(k, {"账户键": k, "户名": k, "开户营业日": "0000-00-00", "币种": "CNY"})
        开户日 = str(户.get("开户营业日") or "")
        问题: list[str] = []
        节点: list[dict[str, Any]] = []
        快照票: list[dict[str, Any]] = []

        
        ar = 快照idx.get((k, anchor))
        if ar and ar.get("状态") == "有效":
            期初余额 = int(ar["余额"])
            锚真实 = True
            节点.append({"角色": "期初锚", "营业日": anchor, "快照存在": True,
                          "余额": 期初余额, "抽取批次编号": ar["抽取批次编号"]})
            快照票.append({"营业日": anchor, "抽取批次编号": ar["抽取批次编号"], "角色": "期初锚"})
        else:
            期初余额 = 0
            锚真实 = False
            开户首日 = bool(开户日) and days[0] == 开户日
            if not 开户首日 and 缺前日策略 != "以零为开端":
                问题.append(f"缺期初锚快照（{anchor}），台参策略={缺前日策略}，不得静默以零开端")
            节点.append({"角色": "期初锚", "营业日": anchor, "快照存在": False,
                          "采用余额": 0, "策略": ("开户首日零开端" if 开户首日 else 缺前日策略)})

        三日净额 = 0
        上日余额: Optional[int] = 期初余额
        期末余额: Optional[int] = None
        for i, day in enumerate(days):
            if 开户日 and day < 开户日:
                节点.append({"角色": f"链日{i+1}", "位置": _位置[i], "营业日": day,
                              "开户前": True, "链环通过": True})
                continue
            net = sum(
                int(f["变动额"])
                for f in 流水
                if f["账户键"] == k and f["营业日"] == day and f["命运"] == "已入账"
            )
            三日净额 += net
            sr = 快照idx.get((k, day))
            有效 = bool(sr and sr.get("状态") == "有效")
            if not 有效:
                问题.append(f"缺{_位置[i]}快照（{day}），链环断裂")
                节点.append({"角色": f"链日{i+1}", "位置": _位置[i], "营业日": day,
                              "快照存在": False, "当日净额": net,
                              "上日余额": 上日余额, "链环通过": False,
                              "原因": "缺当日有效快照"})
                上日余额 = None
                continue

            actual = int(sr["余额"])
            快照票.append({"营业日": day, "位置": _位置[i],
                          "抽取批次编号": sr["抽取批次编号"]})
            if 上日余额 is None:
                link_ok = False
                diff = None
                expected = None
                
            else:
                expected = 上日余额 + net
                diff = actual - expected
                link_ok = diff == 0
                if not link_ok:
                    问题.append(
                        f"{_位置[i]}（{day}）链环不符：上日 {上日余额} + 净额 {net} "
                        f"= {expected}，快照 {actual}，差额 {diff}"
                    )
            节点.append({"角色": f"链日{i+1}", "位置": _位置[i], "营业日": day,
                          "快照存在": True, "快照余额": actual, "上日余额": 上日余额,
                          "当日净额": net, "应得余额": expected, "差额": diff,
                          "链环通过": link_ok,
                          "抽取批次编号": sr["抽取批次编号"]})
            上日余额 = actual
            期末余额 = actual if i == len(days) - 1 else 期末余额

        
        末行 = 快照idx.get((k, days[-1]))
        末有效 = bool(末行 and 末行.get("状态") == "有效")
        if 末有效:
            期末余额 = int(末行["余额"])

        if 末有效:
            连环差额 = 期末余额 - (期初余额 + 三日净额)
            连环通过 = 连环差额 == 0 and not 问题
            if 连环差额 != 0 and not any("连环不符" in p for p in 问题):
                
                if not any("链环不符" in p for p in 问题):
                    问题.append(
                        f"三日连环不符：期初 {期初余额} + 三日净额 {三日净额} "
                        f"= {期初余额 + 三日净额}，期末 {期末余额}，总差额 {连环差额}"
                    )
        else:
            连环差额 = None
            连环通过 = False

        流水票 = sorted({
            str(f["批次编号"])
            for f in 流水
            if f["账户键"] == k and f["批次编号"]
        })
        账户明细.append({
            "账户键": k,
            "户名": 户.get("户名", k),
            "币种": 户.get("币种", "CNY"),
            "开户营业日": 开户日,
            "通过": bool(连环通过),
            "连环通过": bool(连环通过),
            "问题": 问题,
            "节点": 节点,
            "期初锚日": anchor,
            "期初锚真实快照": 锚真实,
            "期初余额": 期初余额,
            "三日净额": 三日净额,
            "期末营业日": days[-1],
            "期末快照存在": 末有效,
            "期末余额": 期末余额,
            "连环差额": 连环差额,
            "同票": {
                "快照抽取票": 快照票,
                "流水装载票": 流水票,
                "回放票": [p for d in days for p in 回放票.get(d, []) if True][:12],
            },
        })

    通过户数 = sum(1 for a in 账户明细 if a["通过"])
    缺日户数 = sum(
        1 for a in 账户明细
        if any("缺" in p and "快照" in p for p in a["问题"])
    )
    return {
        "通过": 通过户数 == len(accounts) and len(accounts) > 0,
        "账户明细": 账户明细,
        "总览": {
            "账户数": len(accounts),
            "通过户数": 通过户数,
            "失败户数": len(accounts) - 通过户数,
            "缺日户数": 缺日户数,
        },
        "同票": {
            "链票": None,  
            "说明": "链号=链式批批次编号；快照/流水/回放票见各户同票",
        },
    }






def 跑三日链(
    账户键们: Optional[list] = None,
    营业日们: Optional[list] = None,
    *,
    末日: str = "",
    营业日: str = "",
    链号: str = "",
    批次编号: str = "",
    交错钩子: Optional[Callable[[dict], None]] = None,
) -> dict[str, Any]:
    """对选定账户跑三日链，同事务写『守恒证明』与『链式批』。

    交错钩子仅供并发/交错夹具在「初采指纹后、提交前」的窗口里，用另一条连接
    执行中日重抽/断档补齐，以确定性验证指纹守卫失败闭。
    """
    days = _解析三日(营业日们, 末日=末日, 营业日=营业日)
    票号 = (链号 or 批次编号 or "").strip()
    链号v = 票号 or f"链-{days[0]}_至_{days[2]}-{uuid.uuid4().hex[:8]}"

    conn = 连接()
    conn.isolation_level = None  
    try:
        确保链表(conn)
        accounts = _选定账户(conn, 账户键们)
        exists = conn.execute("SELECT 1 FROM 守恒证明 WHERE 链号=?", (链号v,)).fetchone()
        if exists:
            raise ValueError(f"链号已存在（证明不可覆盖，重跑请领新号）: {链号v}")

        
        源1, F1 = _采集源(conn, accounts, days)
        明细 = _build_detail(conn, accounts, days, 源1)
        初通过 = bool(明细["通过"])

        
        if callable(交错钩子):
            交错钩子({"链号": 链号v, "初指纹": F1, "营业日们": days, "账户们": accounts})

        
        conn.execute("BEGIN IMMEDIATE")
        源2, F2 = _采集源(conn, accounts, days)
        冲突 = not hmac.compare_digest(F1, F2)
        if 冲突:
            明细 = _build_detail(conn, accounts, days, 源2)
            通过 = False
            原因 = (
                "指纹交错冲突：链初采后、物化前源被改动（疑似中日重抽/断档补齐交错），"
                "旧结论作废，按失败闭落证明；请重新跑链领新证明"
            )
            明细["交错冲突"] = True
            明细["初指纹"] = F1
            明细["提交指纹"] = F2
            存储指纹 = F1
            material_valid = 0
        else:
            通过 = 初通过
            原因 = "" if 通过 else "三日连环守恒不成立，详见账户明细问题项"
            存储指纹 = F1
            material_valid = 1 if 通过 else 0

        明细["链号"] = 链号v
        明细["架构口径"] = 架构口径
        明细["同票"]["链票"] = 链号v
        if 原因:
            明细["结论原因"] = 原因
        时刻 = 此刻()
        明细json = json.dumps(明细, ensure_ascii=False, default=str)
        conn.execute(
            "INSERT INTO 守恒证明(链号,编号,架构口径,营业日们,期初锚日,账户们,通过,valid,"
            "指纹,初指纹,提交指纹,交错冲突,明细,时刻) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                链号v, 链号v, 架构口径, json.dumps(days, ensure_ascii=False),
                源1["期初锚日"], json.dumps(accounts, ensure_ascii=False),
                1 if 通过 else 0, material_valid, 存储指纹, F1, F2,
                1 if 冲突 else 0, 明细json, 时刻,
            ),
        )
        批报告 = {
            "链号": 链号v, "批次编号": 链号v, "通过": 通过, "valid": material_valid,
            "指纹": 存储指纹, "初指纹": F1, "提交指纹": F2,
            "交错冲突": 冲突, "营业日们": days, "账户们": accounts,
            "总览": 明细.get("总览"), "结论原因": 原因,
            
            "权威出处": "守恒证明表",
        }
        conn.execute(
            "INSERT INTO 链式批(链号,编号,营业日们,账户们,状态,时刻,报告) "
            "VALUES (?,?,?,?, '在', ?,?)",
            (链号v, 链号v, json.dumps(days, ensure_ascii=False),
             json.dumps(accounts, ensure_ascii=False), 时刻,
             json.dumps(批报告, ensure_ascii=False)),
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()
    return 核证链(链号v)






def _缺证明对象(链号v: str) -> dict[str, Any]:
    return {
        "链号": 链号v, "chain_id": 链号v, "批次编号": 链号v,
        "存在": False, "记录可读": False,
        "架构口径": 架构口径, "口径说明": _口径说明,
        "通过": False, "通过否": False, "passed": False, "ok": False,
        "原始通过": False,
        "valid": False, "指纹相符": False, "指纹过期": False,
        "指纹": "", "fingerprint": "", "当前指纹": "",
        "交错冲突": False,
        "原因": "无此链号的守恒证明",
        "证明行": None, "链批": None,
    }


def 核证链(链号: str) -> dict[str, Any]:
    key = str(链号 or "").strip()
    if not key:
        raise ValueError("核证须提供链号")
    conn = 连接()
    try:
        确保链表(conn)
        row = conn.execute("SELECT * FROM 守恒证明 WHERE 链号=?", (key,)).fetchone()
        if row is None:
            return _缺证明对象(key)
        d = dict(row)
        days = json.loads(d.get("营业日们") or "[]")
        accounts = json.loads(d.get("账户们") or "[]")
        明细 = json.loads(d.get("明细") or "{}")
        链批row = conn.execute("SELECT * FROM 链式批 WHERE 链号=?", (key,)).fetchone()
        链批 = dict(链批row) if 链批row else None
        if 链批:
            try:
                链批["报告"] = json.loads(链批.get("报告") or "{}")
            except Exception:
                pass

        源, Fnow = _采集源(conn, accounts, days)
        Fstored = d.get("指纹") or ""
        相符 = bool(Fstored) and hmac.compare_digest(Fstored, Fnow)
        原始通过 = bool(d.get("通过"))
        交错冲突 = bool(d.get("交错冲突"))
        
        valid = 原始通过 and 相符 and not 交错冲突
        当前明细 = _build_detail(conn, accounts, days, 源)
        当前源通过 = bool(当前明细["通过"]) and 相符
        证明行 = dict(d)
        证明行["营业日们"] = days
        证明行["账户们"] = accounts
        证明行["明细"] = 明细
        return {
            "链号": key, "chain_id": key,
            "批次编号": key, "ticket": key,
            "存在": True, "记录可读": True,
            "架构口径": d.get("架构口径") or 架构口径,
            "口径说明": _口径说明,
            
            "通过": valid, "通过否": valid, "passed": valid, "ok": valid,
            "原始通过": 原始通过,
            "valid": valid,
            "物化时valid": bool(d.get("valid")),
            "指纹相符": 相符,
            "指纹过期": not 相符,
            "交错冲突": 交错冲突,
            "指纹": Fstored, "fingerprint": Fstored,
            "当前指纹": Fnow,
            "营业日们": days,
            "期初锚日": d.get("期初锚日") or _前日(days[0]) if days else d.get("期初锚日"),
            "账户们": accounts,
            "时刻": d.get("时刻"),
            "总览": 明细.get("总览"),
            "同票": 明细.get("同票", {}),
            "账户明细": 明细.get("账户明细", []),
            "明细": 明细,
            "当前源重算通过": 当前源通过,
            "链批": 链批,
            "链批仍在": 链批 is not None,
            "证明表": "守恒证明",
            "证明行": 证明行,
            "原因": (
                "" if valid else
                ("指纹已过期：中日重抽/断档补齐/删快照使源变动，原通过结论不可采信，请重跑链"
                 if not 相符 else
                 ("该链物化时即为失败/交错冲突，详见明细" if 原始通过 is False else "证明不成立"))
            ),
        }
    finally:
        conn.close()



核证 = 核证链
按链号核证 = 核证链
核证接口 = 核证链
验证链 = 核证链
校验链 = 核证链
跑链 = 跑三日链
执行三日链 = 跑三日链
运行 = 跑三日链


def 取证明(链号: str) -> dict[str, Any]:
    return 核证链(链号)






def 列证明(limit: int = 100) -> list[dict[str, Any]]:
    conn = 连接()
    try:
        确保链表(conn)
        rows = conn.execute(
            "SELECT 链号,编号,架构口径,营业日们,期初锚日,账户们,通过,valid,指纹,"
            "交错冲突,时刻 FROM 守恒证明 ORDER BY rowid DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for k in ("营业日们", "账户们"):
                try:
                    d[k] = json.loads(d.get(k) or "[]")
                except Exception:
                    pass
            d["通过"] = bool(d["通过"])
            d["valid"] = bool(d["valid"])
            d["交错冲突"] = bool(d["交错冲突"])
            out.append(d)
        return out
    finally:
        conn.close()


def 列链批(limit: int = 100) -> list[dict[str, Any]]:
    conn = 连接()
    try:
        确保链表(conn)
        rows = conn.execute(
            "SELECT * FROM 链式批 ORDER BY rowid DESC LIMIT ?", (int(limit),)
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for k in ("营业日们", "账户们"):
                try:
                    d[k] = json.loads(d.get(k) or "[]")
                except Exception:
                    pass
            try:
                d["报告"] = json.loads(d.get("报告") or "{}")
            except Exception:
                pass
            out.append(d)
        return out
    finally:
        conn.close()


def 删除链批(链号: str) -> dict[str, Any]:
    """只删链式批行；独立守恒证明必须仍可按链号核证（口径 A）。"""
    key = str(链号 or "").strip()
    conn = 连接()
    try:
        确保链表(conn)
        cur = conn.execute("DELETE FROM 链式批 WHERE 链号=?", (key,))
        删除数 = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    v = 核证链(key)
    return {
        "链号": key,
        "链批删除行数": int(删除数 or 0),
        "链批已删": True,
        "证明仍可读": bool(v.get("记录可读")),
        "架构口径": 架构口径,
        "核证": v,
    }



删链批 = 删除链批


def 归档链批(链号: str) -> dict[str, Any]:
    key = str(链号 or "").strip()
    conn = 连接()
    try:
        确保链表(conn)
        cur = conn.execute(
            "UPDATE 链式批 SET 状态='已归档' WHERE 链号=?", (key,)
        )
        更新数 = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    v = 核证链(key)
    return {
        "链号": key,
        "归档行数": int(更新数 or 0),
        "链批状态": "已归档",
        "证明仍可读": bool(v.get("记录可读")),
        "架构口径": 架构口径,
        "核证": v,
    }
