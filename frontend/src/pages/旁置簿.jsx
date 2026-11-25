import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function 旁置簿() {
  const [行, set行] = useState([]);
  const [讯, set讯] = useState("");
  useEffect(() => {
    api.旁置().then(set行).catch((e) => set讯(String(e.message || e)));
  }, []);
  return (
    <div>
      <h1 className="题">旁置簿</h1>
      <p className="述">未知账户、字段非法、重复流水号等未入账载荷。</p>
      <div className="行">
        <button className="次" onClick={() => api.旁置().then(set行).catch((e) => set讯(String(e.message || e)))}>刷新</button>
      </div>
      {讯 ? <p className="讯">{讯}</p> : null}
      {!行.length ? <div className="空态">旁置为空</div> : (
        <table>
          <thead><tr><th>原因</th><th>账户键</th><th>营业日</th><th>载荷</th><th>时刻</th></tr></thead>
          <tbody>
            {行.map((r) => (
              <tr key={r.编号}>
                <td>{r.原因}</td><td>{r.账户键 || "—"}</td><td>{r.营业日 || "—"}</td>
                <td style={{ maxWidth: 360, wordBreak: "break-all" }}>{r.载荷}</td><td>{r.时刻}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
