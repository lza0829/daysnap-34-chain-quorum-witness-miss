
"""三日连环守恒 · 链证明测试夹具。

覆盖题目点名的四类夹具 + 删批可读性口径断言：

1. 三日样例跑通、物化证明、台面/接口可展示链号；
2. 删中间日快照再跑必须失败（且仍物化失败证明，禁止只回布尔）；
3. 与中日重抽并发/交错不得用过期指纹报通过（顺序过期 + 确定性交错钩子 + 真线程不变量）；
4. 两账户同跑、一户缺日不得整链假成功；
5. 口径 A 关键断言：删除/归档『链式批』行后，证明仍可按链号读取与核证。

运行：
    cd backend && python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import threading
import unittest


_TMP数据 = tempfile.mkdtemp(prefix="daysnap_chain_test_")
os.environ["数据目录"] = _TMP数据
_FIX = pathlib.Path(__file__).resolve().parents[2] / "fixtures"
if _FIX.exists():
    os.environ["夹具目录"] = str(_FIX)
_BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from app import seed  
from app.db import 连接  
from app.services import 抽取, 装载, 回放  
from app.modules import 三日连环守恒 as 链  
from app.modules.断档补齐 import 补齐缺日  

三日 = ["2026-11-20", "2026-11-21", "2026-11-22"]
夹具目录 = pathlib.Path(os.environ.get("夹具目录", ""))

seed.初始化库()


def 清业务库() -> None:
    conn = 连接()
    try:
        for t in (
            "守恒证明", "链式批", "变动流水", "抽取批次", "周期快照", "回放批次",
            "差额行", "断档记录", "跳变记录", "旁置簿", "装载批次",
        ):
            conn.execute(f"DELETE FROM {t}")
        conn.commit()
    finally:
        conn.close()


def 装三日流水() -> None:
    事件 = [
        {"流水号": "T-甲01", "账户键": "户甲", "营业日": "2026-11-20", "变动额": 10000},
        {"流水号": "T-甲02", "账户键": "户甲", "营业日": "2026-11-20", "变动额": -2500},
        {"流水号": "T-乙01", "账户键": "户乙", "营业日": "2026-11-20", "变动额": 5000},
        {"流水号": "T-甲03", "账户键": "户甲", "营业日": "2026-11-21", "变动额": 3000},
        {"流水号": "T-乙02", "账户键": "户乙", "营业日": "2026-11-21", "变动额": -1000},
        {"流水号": "T-甲04", "账户键": "户甲", "营业日": "2026-11-22", "变动额": -1500},
        {"流水号": "T-乙03", "账户键": "户乙", "营业日": "2026-11-22", "变动额": 2000},
    ]
    r = 装载.装载流水(事件, "测试装载票")
    assert r["入账"] == 7 and r["旁置"] == 0


def 抽三日() -> None:
    for d in 三日:
        抽取.日终抽取(d)


def 直连sql(sql: str, args=()):
    conn = 连接()
    try:
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


class 链测试基(unittest.TestCase):
    def setUp(self) -> None:
        清业务库()
        装三日流水()
        抽三日()


class 三日样例与证明Tests(链测试基):
    def test_三日样例文件本身跑通且有证明(self):
        """直接加载仓库交付的 fixtures/三日连环样例.json。"""
        清业务库()
        data = json.loads((夹具目录 / "三日连环样例.json").read_text(encoding="utf-8"))
        r = 装载.装载流水(data["流水"], data.get("批次编号", "夹具-三日连环"))
        self.assertEqual(r["旁置"], 0)
        for d in 三日:
            抽取.日终抽取(d)
        out = 链.跑三日链(["户甲", "户乙", "户丙"], 三日)
        self.assertIsInstance(out, dict)  
        self.assertTrue(out["通过"], out.get("原因"))
        self.assertTrue(out["valid"])
        self.assertTrue(out["链号"].startswith("链-"))
        self.assertEqual(len(out["指纹"]), 64)
        self.assertEqual(out["架构口径"], 链.架构口径)
        
        conn = 连接()
        try:
            c = conn.execute(
                "SELECT COUNT(*) c FROM 守恒证明 WHERE 链号=?", (out["链号"],)
            ).fetchone()["c"]
        finally:
            conn.close()
        self.assertEqual(c, 1)

    def test_两户样例json跑通(self):
        p = 夹具目录 / "三日连环_两户样例.json"
        self.assertTrue(p.exists(), "须交付两户样例夹具 JSON")
        清业务库()
        data = json.loads(p.read_text(encoding="utf-8"))
        装载.装载流水(data["流水"], data["批次编号"])
        for d in 三日:
            抽取.日终抽取(d)
        out = 链.跑三日链(["户甲", "户乙"], 三日)
        self.assertTrue(out["通过"], out.get("原因"))
        self.assertEqual(out["总览"]["账户数"], 2)

    def test_跑通返回富证据而非布尔(self):
        out = 链.跑三日链(["户甲", "户乙"], 三日)
        for key in ("链号", "通过", "valid", "指纹", "证明行", "账户明细", "同票", "总览"):
            self.assertIn(key, out)
        self.assertIsNotNone(out["证明行"])
        self.assertEqual(out["证明表"], "守恒证明")
        
        for a in out["账户明细"]:
            self.assertEqual(len(a["节点"]), 4)  
            self.assertIn("快照抽取票", a["同票"])
            self.assertTrue(a["通过"])

    def test_链证明与回放同票_回放票被引用(self):
        回放.回放核对("2026-11-21")
        回放.回放核对("2026-11-22")
        out = 链.跑三日链(["户甲"], 三日)
        票 = out["账户明细"][0]["同票"]["回放票"]
        日集 = {x.get("回放批次编号") for x in 票}
        self.assertTrue(any(日集), "应引用已存在的回放批次票")

    def test_核证接口含链号通过否指纹valid(self):
        ran = 链.跑三日链(["户甲"], 三日)
        v = 链.核证链(ran["链号"])
        self.assertEqual(v["链号"], ran["链号"])
        self.assertIn("通过", v)
        self.assertIn("指纹", v)
        self.assertIn("valid", v)
        self.assertTrue(v["valid"])
        self.assertTrue(v["记录可读"])

    def test_未知链号返回富缺失对象而非布尔或404崩溃(self):
        v = 链.核证链("链-不存在-xyz")
        self.assertFalse(v["存在"])
        self.assertFalse(v["记录可读"])
        self.assertFalse(v["通过"])
        self.assertFalse(v["valid"])
        self.assertIsNone(v["证明行"])


class 缺日失败Tests(链测试基):
    def test_删中间日快照再跑必须失败_但仍物化失败证明(self):
        直连sql(
            "DELETE FROM 周期快照 WHERE 账户键='户甲' AND 营业日='2026-11-21'"
        )
        out = 链.跑三日链(["户甲", "户乙"], 三日)
        self.assertFalse(out["通过"])
        self.assertFalse(out["valid"])
        
        self.assertTrue(out["存在"])
        self.assertIsNotNone(out["证明行"])
        self.assertFalse(out["证明行"]["通过"])
        甲 = next(a for a in out["账户明细"] if a["账户键"] == "户甲")
        self.assertFalse(甲["通过"])
        self.assertTrue(any("中日" in p and "2026-11-21" in p for p in 甲["问题"]),
                        甲["问题"])

    def test_删首日或末日快照同样失败(self):
        for day, pos in (("2026-11-20", "首日"), ("2026-11-22", "末日")):
            直连sql("DELETE FROM 周期快照 WHERE 账户键='户甲' AND 营业日=?", (day,))
            out = 链.跑三日链(["户甲"], 三日)
            self.assertFalse(out["通过"], day)
            甲 = out["账户明细"][0]
            self.assertTrue(any(pos in p for p in 甲["问题"]), 甲["问题"])
            抽回 = 抽取.日终抽取(day)  
            self.assertGreaterEqual(抽回["写入"] + 抽回["盖写"], 0)

    def test_期末余额被篡改_连环差额非零且失败(self):
        直连sql(
            "UPDATE 周期快照 SET 余额=99999 WHERE 账户键='户乙' AND 营业日='2026-11-22'"
        )
        out = 链.跑三日链(["户乙"], 三日)
        self.assertFalse(out["通过"])
        乙 = out["账户明细"][0]
        self.assertNotEqual(乙["连环差额"], 0)

    def test_两账户同跑_一户缺日不得整链假成功(self):
        
        直连sql(
            "DELETE FROM 周期快照 WHERE 账户键='户乙' AND 营业日='2026-11-21'"
        )
        out = 链.跑三日链(["户甲", "户乙"], 三日)
        self.assertFalse(out["通过"], "一户缺日时整链必须失败，不得假成功")
        self.assertEqual(out["总览"]["账户数"], 2)
        self.assertEqual(out["总览"]["通过户数"], 1)
        by = {a["账户键"]: a for a in out["账户明细"]}
        self.assertTrue(by["户甲"]["通过"])
        self.assertFalse(by["户乙"]["通过"])
        
        self.assertTrue(by["户甲"]["连环通过"])
        self.assertTrue(any("中日" in p for p in by["户乙"]["问题"]))


class 指纹过期与并发Tests(链测试基):
    def test_中日重抽后_旧链指纹过期_核证不得报通过(self):
        ran = 链.跑三日链(["户甲", "户乙"], 三日)
        self.assertTrue(ran["valid"])
        
        抽取.日终抽取("2026-11-21")
        v = 链.核证链(ran["链号"])
        self.assertFalse(v["指纹相符"])
        self.assertTrue(v["指纹过期"])
        self.assertFalse(v["valid"])
        self.assertFalse(v["通过"], "禁止用过期指纹报通过")
        self.assertTrue(v["原始通过"], "历史结论应保留为曾经通过")
        
        ran2 = 链.跑三日链(["户甲", "户乙"], 三日)
        self.assertNotEqual(ran2["链号"], ran["链号"])
        self.assertTrue(ran2["通过"])
        self.assertTrue(ran2["valid"])
        
        self.assertFalse(链.核证链(ran["链号"])["通过"])

    def test_确定性交错钩子_中日重抽夹在读取与提交之间_失败闭(self):
        def 钩子(ctx):
            
            抽取.日终抽取("2026-11-21")

        out = 链.跑三日链(["户甲", "户乙"], 三日, 交错钩子=钩子)
        self.assertFalse(out["通过"])
        self.assertTrue(out["交错冲突"])
        self.assertFalse(out["valid"])
        v = 链.核证链(out["链号"])
        self.assertFalse(v["通过"])
        self.assertFalse(v["valid"])

    def test_断档补齐交错同样失败闭_补齐后重跑可过(self):
        
        直连sql(
            "DELETE FROM 周期快照 WHERE 账户键='户甲' AND 营业日='2026-11-21'"
        )

        def 钩子(ctx):
            补齐缺日("2026-11-21", "户甲")

        out = 链.跑三日链(["户甲", "户乙"], 三日, 交错钩子=钩子)
        self.assertFalse(out["通过"], "与断档补齐交错必须失败闭")
        self.assertTrue(out["交错冲突"])
        
        again = 链.跑三日链(["户甲", "户乙"], 三日)
        self.assertTrue(again["通过"], again.get("原因"))

    def test_真线程并发_任何核证通过者指纹必相符(self):
        errors: list[str] = []
        stop = threading.Event()

        def 跑链worker():
            try:
                for _ in range(5):
                    r = 链.跑三日链(["户甲", "户乙"], 三日)
                    v = 链.核证链(r["链号"])
                    if v["通过"] and not v["指纹相符"]:
                        errors.append("出现过期指纹却报通过")
                    if v["通过"] and not v["valid"]:
                        errors.append("通过与valid不一致")
            except Exception as e:  
                errors.append(f"跑链异常: {e!r}")

        def 重抽worker():
            try:
                for _ in range(6):
                    抽取.日终抽取("2026-11-21")
            except Exception as e:  
                errors.append(f"重抽异常: {e!r}")
            finally:
                stop.set()

        t1 = threading.Thread(target=跑链worker)
        t2 = threading.Thread(target=重抽worker)
        t1.start(); t2.start()
        t2.join(timeout=30); t1.join(timeout=30)
        self.assertFalse(t1.is_alive(), "跑链线程超时")
        self.assertEqual(errors, [])
        
        for p in 链.列证明(500):
            v = 链.核证链(p["链号"])
            self.assertFalse(v["通过"] and not v["指纹相符"], p["链号"])


class 口径A删批可读性Tests(链测试基):
    """★关键口径分叉断言★

    口径 A（本实现，全局唯一）：结论在独立『守恒证明』表，删/归档链式批行后
    仍可按链号读证明。口径 B（结论只嵌链式批报告、无独立证明表）下，
    ``证明仍可读 is True`` 与 ``证明行 is not None`` 必失败——两口径由此可区分。
    """

    def test_口径A_直接SQL删链式批基表_证明仍可按链号核证(self):
        ran = 链.跑三日链(["户甲", "户乙"], 三日)
        cid = ran["链号"]
        self.assertTrue(ran["valid"])
        n = 直连sql("DELETE FROM 链式批 WHERE 链号=?", (cid,))
        self.assertEqual(n, 1)
        
        self.assertEqual(链.列链批(), [])
        
        v = 链.核证链(cid)
        self.assertTrue(v["存在"])
        self.assertTrue(v["记录可读"])
        self.assertIsNotNone(v["证明行"])
        self.assertFalse(v["链批仍在"])
        self.assertIsNone(v["链批"])
        self.assertTrue(v["指纹相符"])
        self.assertTrue(v["valid"])
        self.assertTrue(v["通过"])

    def test_口径A_删除接口返回富对象且证明仍可读(self):
        ran = 链.跑三日链(["户甲"], 三日)
        d = 链.删除链批(ran["链号"])
        self.assertEqual(d["链批删除行数"], 1)
        self.assertTrue(d["证明仍可读"])
        self.assertTrue(d["核证"]["valid"])
        self.assertTrue(d["核证"]["记录可读"])

    def test_口径A_归档后证明仍可读(self):
        ran = 链.跑三日链(["户甲"], 三日)
        a = 链.归档链批(ran["链号"])
        self.assertEqual(a["归档行数"], 1)
        self.assertTrue(a["证明仍可读"])
        self.assertTrue(a["核证"]["valid"])
        b = next(x for x in 链.列链批() if x["链号"] == ran["链号"])
        self.assertEqual(b["状态"], "已归档")

    def test_口径区分_证明是独立基表而非视图或报告字段(self):
        conn = 连接()
        try:
            typ = conn.execute(
                "SELECT type FROM sqlite_master WHERE name='守恒证明'"
            ).fetchone()["type"]
        finally:
            conn.close()
        self.assertEqual(typ, "table", "口径 A 要求 守恒证明 是独立基表")

    def test_同义视图名删除链批也落到基表(self):
        ran = 链.跑三日链(["户甲"], 三日)
        cid = ran["链号"]
        
        
        直连sql("DELETE FROM 连环链式批 WHERE 链号=?", (cid,))
        self.assertIsNone(
            next((b for b in 链.列链批() if b["链号"] == cid), None)
        )
        self.assertTrue(链.核证链(cid)["记录可读"])


def _有httpx() -> bool:
    import importlib.util
    return bool(importlib.util.find_spec("httpx")) and bool(
        importlib.util.find_spec("fastapi.testclient")
    )


@unittest.skipUnless(_有httpx(), "需要 httpx 才能跑接口级测试")
class 接口Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from app.main import app
        cls.client = TestClient(app)

    def setUp(self):
        清业务库()
        装三日流水()
        抽三日()

    def test_HTTP_跑链_核证_删批_全链路(self):
        c = self.client
        r = c.post("/api/连环守恒/跑链", json={"账户键们": ["户甲", "户乙"], "营业日们": 三日})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["通过"])
        cid = body["链号"]

        g = c.get(f"/api/连环守恒/核证/{cid}")
        self.assertEqual(g.status_code, 200)
        self.assertTrue(g.json()["valid"])
        self.assertIn("指纹", g.json())

        
        g2 = c.get("/api/连环守恒/核证", params={"链号": cid})
        self.assertTrue(g2.json()["valid"])

        
        d = c.delete(f"/api/连环守恒/链批/{cid}")
        self.assertEqual(d.status_code, 200)
        self.assertTrue(d.json()["证明仍可读"])
        g3 = c.get(f"/api/连环守恒/核证/{cid}")
        self.assertTrue(g3.json()["记录可读"])

    def test_HTTP_缺日失败与重抽过期(self):
        c = self.client
        直连sql("DELETE FROM 周期快照 WHERE 账户键='户乙' AND 营业日='2026-11-21'")
        r = c.post("/api/连环守恒/跑链", json={"账户键们": ["户甲", "户乙"], "营业日们": 三日}).json()
        self.assertFalse(r["通过"])
        self.assertIsNotNone(r["证明行"])

        
        抽取.日终抽取("2026-11-21")
        ok = c.post("/api/连环守恒/跑链", json={"账户键们": ["户甲"], "营业日们": 三日}).json()
        self.assertTrue(ok["通过"])
        抽取.日终抽取("2026-11-21")
        v = c.get(f"/api/连环守恒/核证/{ok['链号']}").json()
        self.assertFalse(v["valid"])
        self.assertFalse(v["通过"])

    def test_HTTP_台面总览含最近链号(self):
        c = self.client
        r = c.post("/api/连环守恒/跑链", json={"账户键们": ["户甲"], "营业日们": 三日}).json()
        o = c.get("/api/总览").json()
        self.assertGreaterEqual(o["连环证明数"], 1)
        self.assertEqual(o["最近链号"], r["链号"])

    def test_HTTP_标量营业日视作末日前推两日(self):
        c = self.client
        
        r = c.post("/api/连环守恒/跑链", json={"账户键们": ["户甲", "户乙"], "营业日": "2026-11-22"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["营业日们"], 三日)
        self.assertTrue(body["通过"], body)

        
        r2 = c.post("/api/连环守恒/跑链", json={"accounts": "户甲", "days": ["2026-11-22"]})
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertTrue(r2.json()["通过"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
