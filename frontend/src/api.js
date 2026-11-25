async function 请求(path, opts = {}) {
  const r = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  const text = await r.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!r.ok) {
    const msg = (data && data.detail) || text || r.statusText;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

export const api = {
  健康: () => 请求("/健康"),
  总览: () => 请求("/总览"),
  台参: () => 请求("/台参"),
  账户: () => 请求("/账户"),
  流水: (q = "") => 请求(`/流水${q}`),
  快照: (q = "") => 请求(`/快照${q}`),
  差额: (q = "") => 请求(`/差额${q}`),
  断档: () => 请求("/断档"),
  跳变: () => 请求("/跳变"),
  旁置: () => 请求("/旁置"),
  夹具: () => 请求("/夹具"),
  装载批次: () => 请求("/装载批次"),
  抽取批次: () => 请求("/抽取批次"),
  回放批次: () => 请求("/回放批次"),
  装载夹具: (名) => 请求("/装载夹具", { method: "POST", body: JSON.stringify({ 名 }) }),
  抽取: (营业日) => 请求("/抽取", { method: "POST", body: JSON.stringify({ 营业日 }) }),
  回放: (营业日) => 请求("/回放", { method: "POST", body: JSON.stringify({ 营业日 }) }),
  重置: () => 请求("/重置业务库", { method: "POST", body: "{}" }),

  跑连环链: (body) =>
    请求("/连环守恒/跑链", { method: "POST", body: JSON.stringify(body || {}) }),
  核证连环: (链号) =>
    请求(`/连环守恒/核证/${encodeURIComponent(链号)}`),
  连环证明列表: () => 请求("/连环守恒/证明"),
  连环链批列表: () => 请求("/连环守恒/链批"),
  删连环链批: (链号) =>
    请求(`/连环守恒/链批/${encodeURIComponent(链号)}`, { method: "DELETE" }),
  归档连环链批: (链号) =>
    请求(`/连环守恒/链批/${encodeURIComponent(链号)}/归档`, { method: "POST" }),
  断档补齐: (body) =>
    请求("/断档补齐", { method: "POST", body: JSON.stringify(body) }),
};
