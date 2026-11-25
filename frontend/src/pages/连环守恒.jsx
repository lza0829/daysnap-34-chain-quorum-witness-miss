import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";

function 徽章({ ok, 真, 假 }) {
  return <span className={`徽章 ${ok ? "通" : "败"}`}>{ok ? 真 : 假}</span>;
}

function 钱(n) {
  if (n === null || n === undefined) return "—";
  return Number(n).toLocaleString("zh-CN");
}

export default function 连环守恒() {
  const [账户, set账户] = useState([]);
  const [选中, set选中] = useState([]);
  const [d0, setD0] = useState("2026-11-20");
  const [d1, setD1] = useState("2026-11-21");
  const [d2, setD2] = useState("2026-11-22");
  const [链号输入, set链号输入] = useState("");
  const [结果, set结果] = useState(null);
  const [证明, set证明] = useState([]);
  const [链批, set链批] = useState([]);
  const [讯, set讯] = useState("");
  const [忙, set忙] = useState(false);

  const days = useMemo(() => [d0, d1, d2].map((s) => s.trim()).filter(Boolean), [d0, d1, d2]);

  const 刷新列表 = async () => {
    const [ps, bs] = await Promise.all([api.连环证明列表(), api.连环链批列表()]);
    set证明(ps);
    set链批(bs);
  };

  useEffect(() => {
    api
      .账户()
      .then((rows) => {
        set账户(rows);
        const prefer = rows.filter((r) => ["户甲", "户乙"].includes(r.账户键)).map((r) => r.账户键);
        set选中(prefer.length ? prefer : rows.slice(0, 2).map((r) => r.账户键));
      })
      .catch((e) => set讯(String(e.message || e)));
    刷新列表().catch((e) => set讯(String(e.message || e)));
  }, []);

  const 切户 = (k) =>
    set选中((s) => (s.includes(k) ? s.filter((x) => x !== k) : [...s, k]));

  const 跑链 = async () => {
    set忙(true);
    set讯("");
    try {
      const r = await api.跑连环链({ 账户键们: 选中, 营业日们: days });
      set结果(r);
      set链号输入(r.链号);
      await 刷新列表();
    } catch (e) {
      set讯(String(e.message || e));
    } finally {
      set忙(false);
    }
  };

  const 核证 = async (id) => {
    const key = (id ?? 链号输入).trim();
    if (!key) {
      set讯("请先给链号");
      return;
    }
    set忙(true);
    set讯("");
    try {
      const v = await api.核证连环(key);
      set结果(v);
      set链号输入(key);
      if (!v.存在) set讯(`查无证明：${key}`);
    } catch (e) {
      set讯(String(e.message || e));
    } finally {
      set忙(false);
    }
  };

  const 删批 = async (id) => {
    if (!window.confirm(`只删除链式批行 ${id}？口径 A 下独立证明仍应可核证。`)) return;
    set忙(true);
    set讯("");
    try {
      const r = await api.删连环链批(id);
      set结果(r.核证);
      set链号输入(id);
      set讯(`链式批已删 ${r.链批删除行数} 行；证明仍可读=${r.证明仍可读}`);
      await 刷新列表();
    } catch (e) {
      set讯(String(e.message || e));
    } finally {
      set忙(false);
    }
  };

  const 归档 = async (id) => {
    set忙(true);
    try {
      const r = await api.归档连环链批(id);
      set结果(r.核证);
      set讯(`已归档；证明仍可读=${r.证明仍可读}`);
      await 刷新列表();
    } catch (e) {
      set讯(String(e.message || e));
    } finally {
      set忙(false);
    }
  };

  const r = 结果;

  return (
    <div>
      <h1 className="题">三日连环守恒 · 链证明</h1>
      <p className="述">
        对选定账户核「期初锚 + 三日净额 = 期末镜」并逐环闭合，同事务物化独立
        <b> 守恒证明 </b> 与 <b>链式批</b>。架构口径 A：证明独立落表，删/归档链式批后仍可按链号回看核证；
        缺日、中日重抽、断档补齐交错致指纹过期时失败闭，绝不用旧指纹报通过，也不只回布尔。
      </p>

      <div className="提示条">
        口径：{r?.架构口径 || "A-守恒证明表为准"}　|　链号即同票批次号，指纹覆盖三日快照（含抽取票）、流水、断档与源纪元。
      </div>

      <div className="段">
        <h2 className="段题">① 选账户 × 三个营业日跑链</h2>
        <div className="行">
          {账户.map((a) => (
            <label key={a.账户键} className="勾选">
              <input type="checkbox" checked={选中.includes(a.账户键)} onChange={() => 切户(a.账户键)} />
              {a.账户键}
            </label>
          ))}
        </div>
        <div className="行">
          <input value={d0} onChange={(e) => setD0(e.target.value)} aria-label="首日" />
          <input value={d1} onChange={(e) => setD1(e.target.value)} aria-label="中日" />
          <input value={d2} onChange={(e) => setD2(e.target.value)} aria-label="末日" />
          <button className="水" disabled={忙 || !选中.length || days.length !== 3} onClick={跑链}>
            {忙 ? "跑着…" : "跑三日链并物化证明"}
          </button>
        </div>
      </div>

      <div className="段">
        <h2 className="段题">② 按链号核证 / 回看</h2>
        <div className="行">
          <input
            className="链号输入"
            value={链号输入}
            onChange={(e) => set链号输入(e.target.value)}
            placeholder="链-2026-11-20_至_2026-11-22-xxxxxxxx"
          />
          <button disabled={忙} onClick={() => 核证()}>核证</button>
        </div>
        {讯 ? <p className="讯">{讯}</p> : null}
      </div>

      {r ? (
        <div className="证卡">
          <div className="证头">
            <div>
              <span className="链号" title="链号">{r.链号}</span>
              <div className="证次">
                {r.存在 === false ? (
                  <徽章 ok={false} 真="" 假="无证明" />
                ) : (
                  <>
                    <徽章 ok={!!r.通过} 真="当前核证通过" 假="当前不通过" />
                    <span style={{ marginLeft: 8 }}>
                      valid <徽章 ok={!!r.valid} 真="true" 假="false" />
                    </span>
                    {r.原始通过 !== undefined && r.原始通过 !== r.通过 ? (
                      <span className="淡注">（落库原始通过={String(r.原始通过)}，指纹已过期/冲突，结论不可采信）</span>
                    ) : null}
                  </>
                )}
              </div>
            </div>
            <div className="证meta">
              <div>架构：{r.架构口径}</div>
              <div>时刻：{r.时刻 || "—"}</div>
              <div>链式批：{r.链批仍在 ? "在" : "已删/无"}</div>
            </div>
          </div>

          {r.原因 ? <p className="败因">{r.原因}</p> : null}
          {r.总览 ? (
            <div className="行" style={{ marginTop: 6 }}>
              <span className="小阶">账户 {r.总览.账户数}</span>
              <span className="小阶 通">通过 {r.总览.通过户数}</span>
              <span className="小阶 败">失败 {r.总览.失败户数}</span>
              <span className="小阶 败">缺日 {r.总览.缺日户数}</span>
              <span className="小阶">指纹相符 {String(r.指纹相符)}</span>
              <span className="小阶">交错冲突 {String(!!r.交错冲突)}</span>
            </div>
          ) : null}

          <div className="指纹行">
            <span>落库指纹：</span>
            <code title={r.指纹}>{r.指纹 || "—"}</code>
          </div>
          {r.当前指纹 && r.当前指纹 !== r.指纹 ? (
            <div className="指纹行">
              <span>当前指纹：</span>
              <code title={r.当前指纹}>{r.当前指纹}</code>
            </div>
          ) : null}

          {Array.isArray(r.账户明细) && r.账户明细.length ? (
            <table style={{ marginTop: 10 }}>
              <thead>
                <tr>
                  <th>账户</th><th>结论</th><th>期初锚</th><th>三日净额</th>
                  <th>期末镜</th><th>连环差额</th><th>问题 / 同票</th>
                </tr>
              </thead>
              <tbody>
                {r.账户明细.map((a) => (
                  <tr key={a.账户键}>
                    <td>{a.账户键}</td>
                    <td><徽章 ok={!!a.通过} 真="通过" 假="失败" /></td>
                    <td>{钱(a.期初余额)}{a.期初锚真实快照 ? "" : "（零开端）"}</td>
                    <td>{钱(a.三日净额)}</td>
                    <td>{钱(a.期末余额)}</td>
                    <td className={a.连环差额 ? "数败" : "数通"}>{钱(a.连环差额)}</td>
                    <td>
                      {a.问题?.length ? <div className="败因">{a.问题.join("；")}</div> : <div className="淡注">三环闭合</div>}
                      <div className="淡注">
                        抽取票 {a.同票?.快照抽取票?.map((t) => t.抽取批次编号).join("，") || "—"}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </div>
      ) : (
        <div className="空态">尚未跑链或核证</div>
      )}

      <div className="段">
        <h2 className="段题">③ 证明按链号回看（独立证明表）</h2>
        {!证明.length ? (
          <div className="空态">尚无链证明</div>
        ) : (
          <table>
            <thead>
              <tr><th>链号</th><th>三日</th><th>账户</th><th>通过</th><th>物化valid</th><th>指纹</th><th>时刻</th></tr>
            </thead>
            <tbody>
              {证明.map((p) => (
                <tr key={p.链号} className="可点" onClick={() => 核证(p.链号)}>
                  <td className="链号">{p.链号}</td>
                  <td>{Array.isArray(p.营业日们) ? p.营业日们.join(" / ") : ""}</td>
                  <td>{Array.isArray(p.账户们) ? p.账户们.join(",") : ""}</td>
                  <td><徽章 ok={p.通过} 真="通过" 假="失败" /></td>
                  <td>{String(p.valid)}</td>
                  <td><code className="短指纹">{(p.指纹 || "").slice(0, 12)}…</code></td>
                  <td>{p.时刻}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="段">
        <h2 className="段题">④ 链式批行（归档/删除后，证明仍应可读）</h2>
        {!链批.length ? (
          <div className="空态">无链式批行（可能已删批；上方证明仍可按链号核证）</div>
        ) : (
          <table>
            <thead>
              <tr><th>链号</th><th>状态</th><th>报告通过</th><th>时刻</th><th>操作</th></tr>
            </thead>
            <tbody>
              {链批.map((b) => (
                <tr key={b.链号}>
                  <td className="链号">{b.链号}</td>
                  <td>{b.状态}</td>
                  <td>{String(b.报告?.通过)}</td>
                  <td>{b.时刻}</td>
                  <td>
                    <button className="次 小钮" onClick={() => 核证(b.链号)}>核证</button>{" "}
                    <button className="次 小钮" onClick={() => 归档(b.链号)}>归档</button>{" "}
                    <button className="危 小钮" onClick={() => 删批(b.链号)}>删批</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
