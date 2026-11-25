import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function 变动流水() {
  const [夹具, set夹具] = useState([]);
  const [选, set选] = useState("三日连环样例.json");
  const [行, set行] = useState([]);
  const [讯, set讯] = useState("");

  const 刷新 = async () => {
    set行(await api.流水());
    set夹具(await api.夹具());
  };

  useEffect(() => {
    刷新().catch((e) => set讯(String(e.message || e)));
  }, []);

  return (
    <div>
      <h1 className="题">变动流水</h1>
      <p className="述">装入账户增减流水，供日终抽取累计。</p>
      <div className="行">
        <select value={选} onChange={(e) => set选(e.target.value)}>
          {夹具.map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
        <button
          onClick={() =>
            api
              .装载夹具(选)
              .then((r) => set讯(`装载完成 入账=${r.入账} 旁置=${r.旁置}`))
              .then(刷新)
              .catch((e) => set讯(String(e.message || e)))
          }
        >
          装载夹具
        </button>
        <button className="次" onClick={() => 刷新().catch((e) => set讯(String(e.message || e)))}>刷新</button>
      </div>
      {讯 ? <p className="讯">{讯}</p> : null}
      {!行.length ? (
        <div className="空态">暂无流水</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>流水号</th>
              <th>账户键</th>
              <th>营业日</th>
              <th>变动额</th>
              <th>摘要</th>
              <th>命运</th>
            </tr>
          </thead>
          <tbody>
            {行.map((r) => (
              <tr key={r.流水号}>
                <td>{r.流水号}</td>
                <td>{r.账户键}</td>
                <td>{r.营业日}</td>
                <td>{r.变动额}</td>
                <td>{r.摘要}</td>
                <td>{r.命运}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
