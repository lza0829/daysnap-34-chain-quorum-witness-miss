import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function 账户册() {
  const [行, set行] = useState([]);
  const [讯, set讯] = useState("");
  useEffect(() => {
    api.账户().then(set行).catch((e) => set讯(String(e.message || e)));
  }, []);
  return (
    <div>
      <h1 className="题">账户册</h1>
      <p className="述">种子账户。金额单位为分。</p>
      {讯 ? <p className="讯">{讯}</p> : null}
      {!行.length ? (
        <div className="空态">暂无账户</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>账户键</th>
              <th>户名</th>
              <th>币种</th>
              <th>开户营业日</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {行.map((r) => (
              <tr key={r.账户键}>
                <td>{r.账户键}</td>
                <td>{r.户名}</td>
                <td>{r.币种}</td>
                <td>{r.开户营业日}</td>
                <td>{r.状态}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
