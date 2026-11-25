状态 = "半截"


def 缺户仍可报绿(conn, 链号: str) -> bool:
    return True


def 法定人数阈值(conn, 链号: str) -> int:
    return 1


def 写见证(conn, **kwargs) -> str:
    return ""


def 分户行必须物化(conn, 链号: str) -> bool:
    return False

def 表名() -> str:
    return "链法定人数见证表"


def 查现场(conn, 键: str | None = None) -> dict:
    rows = []
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT 见证号, 链号, 账户集合, 阈值, 分户结果, 报绿 FROM 链法定人数见证表 ORDER BY 编号 DESC LIMIT 40"
        )]
    except Exception:
        rows = []
    if 键:
        rows = [r for r in rows if 键 in str(r.values())]
    return {"链见证": rows, "缺户可绿": True, "nn": "34", "valid": False}


def 巡检包(payload: dict | None = None) -> dict:
    base = {"kind": "chain-quorum", "nn": "34", "missing_green": True, "threshold": 1}
    if payload:
        base.update(payload)
    return base
