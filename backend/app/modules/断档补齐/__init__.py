"""断档补齐（邻题扩展点落地）。

补齐某个缺失营业日的快照：复用日终抽取（前日镜 + 当日已入账流水），
并把对应『缺营业日』的断档记录处置更新为『已补齐』。

它是三日连环守恒交错守卫的协同方：补齐会写快照并推进源纪元，
因此若与跑链交错，链指纹前后不一致即失败闭，不会拿旧指纹报通过。
"""

from __future__ import annotations

import uuid
from typing import Any

from app.db import 连接
from app.services import 抽取
from app.services.时间 import 标准化营业日

启用 = True


def 说明() -> str:
    return "断档补齐：补写缺日快照并核销对应断档记录；与三日链交错时由指纹守卫失败闭"


def 补齐缺日(营业日: str, 账户键: str = "", 批次编号: str = "") -> dict[str, Any]:
    """补齐缺日快照。

    抽取服务按既有语义对全部正常账户写该日快照；若给了账户键，则断档核销
    只针对该户。返回富证据（不得只回布尔）。
    """
    日 = 标准化营业日(营业日)
    批 = (批次编号 or "").strip() or f"补齐-{日}-{uuid.uuid4().hex[:8]}"
    抽取报告 = 抽取.日终抽取(日, 批)

    conn = 连接()
    try:
        if 账户键.strip():
            cur = conn.execute(
                "UPDATE 断档记录 SET 处置='已补齐' "
                "WHERE 缺营业日=? AND 账户键=? AND COALESCE(处置,'')!='已补齐'",
                (日, 账户键.strip()),
            )
        else:
            cur = conn.execute(
                "UPDATE 断档记录 SET 处置='已补齐' "
                "WHERE 缺营业日=? AND COALESCE(处置,'')!='已补齐'",
                (日,),
            )
        核销 = cur.rowcount
        conn.commit()
    finally:
        conn.close()

    return {
        "营业日": 日,
        "账户键": 账户键.strip() or "(全部账户)",
        "批次编号": 批,
        "核销断档数": int(核销 or 0),
        "抽取": 抽取报告,
        "提示": "补齐已改变快照源与源纪元；此前三日链证明指纹会过期，须重跑链核证",
    }
