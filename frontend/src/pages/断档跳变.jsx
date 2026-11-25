import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function 断档跳变() {
  const [断档, set断档] = useState([]);
  const [跳变, set跳变] = useState([]);
  const [讯, set讯] = useState("");
  const 刷新 = async () => {
    set断档(await api.断档());
    set跳变(await api.跳变());
  };
  useEffect(() => {
    刷新().catch((e) => set讯(String(e.message || e)));
  }, []);
  return (
    <div>
      <h1 className="题">断档跳变</h1>
      <p className="述">缺前日快照记断档；偏离超过台参阈值记跳变。</p>
      <div className="行">
        <button className="次" onClick={() => 刷新().catch((e) => set讯(String(e.message || e)))}>刷新</button>
      </div>
      {讯 ? <p className="讯">{讯}</p> : null}
      <div className="段">
        <h2 className="段题">断档记录</h2>
        {!断档.length ? <div className="空态">无断档</div> : (
          <table>
            <thead><tr><th>账户键</th><th>缺营业日</th><th>处置</th><th>批次</th><th>时刻</th></tr></thead>
            <tbody>
              {断档.map((r) => (
                <tr key={r.编号}>
                  <td>{r.账户键}</td><td>{r.缺营业日}</td><td>{r.处置}</td><td>{r.检出批次编号}</td><td>{r.时刻}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <div className="段">
        <h2 className="段题">跳变记录</h2>
        {!跳变.length ? <div className="空态">无跳变</div> : (
          <table>
            <thead><tr><th>账户键</th><th>营业日</th><th>前日</th><th>当日</th><th>流水净额</th><th>偏离</th></tr></thead>
            <tbody>
              {跳变.map((r) => (
                <tr key={r.编号}>
                  <td>{r.账户键}</td><td>{r.营业日}</td><td>{r.前日余额}</td><td>{r.当日余额}</td><td>{r.流水净额}</td><td>{r.偏离}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
