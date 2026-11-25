import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function 差额清单() {
  const [行, set行] = useState([]);
  const [讯, set讯] = useState("");
  useEffect(() => {
    api.差额().then(set行).catch((e) => set讯(String(e.message || e)));
  }, []);
  return (
    <div>
      <h1 className="题">差额清单</h1>
      <p className="述">快照余额与回放余额不一致时落在这里；冒烟通过时应为空或仅历史批。</p>
      <div className="行">
        <button className="次" onClick={() => api.差额().then(set行).catch((e) => set讯(String(e.message || e)))}>
          刷新
        </button>
      </div>
      {讯 ? <p className="讯">{讯}</p> : null}
      {!行.length ? (
        <div className="空态">暂无差额行</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>回放批次</th>
              <th>账户键</th>
              <th>营业日</th>
              <th>快照余额</th>
              <th>回放余额</th>
              <th>差额</th>
              <th>原因</th>
            </tr>
          </thead>
          <tbody>
            {行.map((r) => (
              <tr key={r.编号}>
                <td>{r.回放批次编号}</td>
                <td>{r.账户键}</td>
                <td>{r.营业日}</td>
                <td>{r.快照余额 ?? "—"}</td>
                <td>{r.回放余额 ?? "—"}</td>
                <td>{r.差额}</td>
                <td>{r.原因}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
