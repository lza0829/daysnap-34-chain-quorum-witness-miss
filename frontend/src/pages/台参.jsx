import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function 台参() {
  const [参, set参] = useState({});
  const [讯, set讯] = useState("");
  useEffect(() => {
    api.台参().then(set参).catch((e) => set讯(String(e.message || e)));
  }, []);
  const 行 = Object.entries(参);
  return (
    <div>
      <h1 className="题">台参</h1>
      <p className="述">运行参数只读展示；邻题可扩展可写策略。</p>
      {讯 ? <p className="讯">{讯}</p> : null}
      {!行.length ? <div className="空态">无台参</div> : (
        <table>
          <thead><tr><th>键</th><th>值</th></tr></thead>
          <tbody>
            {行.map(([k, v]) => (
              <tr key={k}><td>{k}</td><td>{v}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
