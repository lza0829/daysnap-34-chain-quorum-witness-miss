import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";

const 三日 = ["2026-11-20", "2026-11-21", "2026-11-22"];

export default function 台面() {
  const [总览, set总览] = useState(null);
  const [讯, set讯] = useState("");
  const [忙, set忙] = useState(false);
  const [链号, set链号] = useState("");
  const [核证号, set核证号] = useState("");
  const [核证, set核证] = useState(null);

  const 刷新 = async () => {
    set总览(await api.总览());
  };

  useEffect(() => {
    刷新()
      .then(() => api.总览().then((o) => o.最近链号 && set链号(o.最近链号)))
      .catch((e) => set讯(String(e.message || e)));
  }, []);

  const 冒烟 = async () => {
    set忙(true);
    set讯("");
    set核证(null);
    try {
      await api.重置();
      await api.装载夹具("三日连环样例.json");
      const a = await api.抽取("2026-11-20");
      const b = await api.抽取("2026-11-21");
      const c = await api.抽取("2026-11-22");
      const r = await api.回放("2026-11-22");
      const chain = await api.跑连环链({ 账户键们: ["户甲", "户乙", "户丙"], 营业日们: 三日 });
      set链号(chain.链号);
      set核证号(chain.链号);
      set核证(chain);
      await 刷新();
      set讯(
        `冒烟完成：抽取 ${a.写入 + a.盖写}/${b.写入 + b.盖写}/${c.写入 + c.盖写}；` +
          `单日回放通过=${r.通过} 差额=${r.差额}；三日链通过=${chain.通过} valid=${chain.valid} 链号=${chain.链号}`
      );
    } catch (e) {
      set讯(String(e.message || e));
    } finally {
      set忙(false);
    }
  };

  const 按链号核证 = async () => {
    if (!核证号.trim()) return;
    set忙(true);
    try {
      const v = await api.核证连环(核证号.trim());
      set核证(v);
      set链号(v.链号);
      set讯(v.存在 ? `已按链号核证：通过=${v.通过} valid=${v.valid}` : "查无此链号证明");
    } catch (e) {
      set讯(String(e.message || e));
    } finally {
      set忙(false);
    }
  };

  const o = 总览 || {};
  return (
    <div>
      <h1 className="题">台面</h1>
      <p className="述">先装流水，再按营业日做日终抽取写周期快照，最后回放核对看差额清单是否清空；三日链再核「期初+净额=期末」并物化可按链号回看的证明。</p>
      <div className="提示条">
        最短路径：点「一键冒烟（含三日链）」→ 看本页链号 → 打开{" "}
        <Link to="/连环守恒">⑥ 三日连环链证</Link> 按链号回看，或进 <Link to="/周期快照">周期快照</Link> 与{" "}
        <Link to="/差额清单">差额清单</Link>。
      </div>
      <div className="阶条">
        <div className="阶"><div className="序">账户</div><b>{o.账户数 ?? "—"}</b><span>册内户数</span></div>
        <div className="阶"><div className="序">流水</div><b>{o.流水数 ?? "—"}</b><span>已入账</span></div>
        <div className="阶"><div className="序">快照</div><b>{o.快照数 ?? "—"}</b><span>有效行</span></div>
        <div className="阶"><div className="序">差额</div><b>{o.差额行数 ?? "—"}</b><span>清单行</span></div>
        <div className="阶"><div className="序">链证明</div><b>{o.连环证明数 ?? "—"}</b><span>通过 {o.连环通过数 ?? 0}</span></div>
      </div>
      <div className="行">
        <button disabled={忙} onClick={冒烟}>{忙 ? "跑着…" : "一键冒烟（含三日链）"}</button>
        <button className="次" onClick={() => 刷新().catch((e) => set讯(String(e.message || e)))}>刷新总览</button>
        <button
          className="次"
          onClick={() =>
            api.重置().then(刷新).then(() => { set核证(null); set讯("已清空业务表"); }).catch((e) => set讯(String(e.message || e)))
          }
        >
          清空业务表
        </button>
      </div>

      <div className="链查条">
        <span className="淡">按链号核证/回看：</span>
        <input
          className="链号输入"
          value={核证号}
          onChange={(e) => set核证号(e.target.value)}
          placeholder="链-2026-11-20_至_2026-11-22-xxxxxxxx"
        />
        <button className="水" disabled={忙} onClick={按链号核证}>核证</button>
        {链号 ? (
          <Link className="链号链接" to="/连环守恒">
            最近链号：<span className="链号">{链号}</span>
          </Link>
        ) : null}
      </div>

      {核证 ? (
        <div className="证卡 紧">
          <div className="证头">
            <span className="链号">{核证.链号}</span>
            <span className={`徽章 ${核证.通过 ? "通" : "败"}`}>
              {核证.存在 === false ? "无证明" : 核证.通过 ? "核证通过" : "核证不通过"}
            </span>
            <span className="淡注">valid={String(核证.valid)}</span>
            {核证.指纹过期 ? <span className="徽章 败">指纹过期</span> : null}
            {核证.交错冲突 ? <span className="徽章 败">交错冲突</span> : null}
          </div>
          {核证.原因 ? <p className="败因">{核证.原因}</p> : null}
        </div>
      ) : null}

      {讯 ? <p className="讯">{讯}</p> : null}
    </div>
  );
}
