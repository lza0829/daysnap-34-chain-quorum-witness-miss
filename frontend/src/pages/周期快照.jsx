import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function 周期快照() {
  const [日, set日] = useState("");
  const [行, set行] = useState([]);
  const [讯, set讯] = useState("");

  const 刷新 = () => api.快照(日 ? `?营业日=${encodeURIComponent(日)}` : "").then(set行);

  useEffect(() => {
    刷新().catch((e) => set讯(String(e.message || e)));
  }, []);

  return (
    <div>
      <h1 className="题">周期快照</h1>
      <p className="述">每个账户每个营业日一行有效余额镜。</p>
      <div className="行">
        <input value={日} onChange={(e) => set日(e.target.value)} placeholder="筛选营业日，可空" />
        <button className="次" onClick={() => 刷新().catch((e) => set讯(String(e.message || e)))}>刷新</button>
      </div>
      {讯 ? <p className="讯">{讯}</p> : null}
      {!行.length ? (
        <div className="空态">暂无快照</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>账户键</th>
              <th>营业日</th>
              <th>余额</th>
              <th>抽取批次</th>
              <th>来源</th>
            </tr>
          </thead>
          <tbody>
            {行.map((r) => (
              <tr key={r.快照键}>
                <td>{r.账户键}</td>
                <td>{r.营业日}</td>
                <td>{r.余额}</td>
                <td>{r.抽取批次编号}</td>
                <td>{r.来源}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
