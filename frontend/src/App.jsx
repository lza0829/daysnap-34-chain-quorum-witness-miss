import React from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import 台面 from "./pages/台面.jsx";
import 账户册 from "./pages/账户册.jsx";
import 变动流水 from "./pages/变动流水.jsx";
import 日终抽取 from "./pages/日终抽取.jsx";
import 周期快照 from "./pages/周期快照.jsx";
import 回放核对 from "./pages/回放核对.jsx";
import 连环守恒 from "./pages/连环守恒.jsx";
import 差额清单 from "./pages/差额清单.jsx";
import 断档跳变 from "./pages/断档跳变.jsx";
import 旁置簿 from "./pages/旁置簿.jsx";
import 台参 from "./pages/台参.jsx";
import 核证链见证 from "./pages/链见证.jsx";

const 主链 = [
  ["/", "台面"],
  ["/账户册", "① 账户册"],
  ["/变动流水", "② 变动流水"],
  ["/日终抽取", "③ 日终抽取"],
  ["/周期快照", "④ 周期快照"],
  ["/回放核对", "⑤ 回放核对"],
  ["/连环守恒", "⑥ 三日连环链证"],
  ["/差额清单", "差额清单"],
];
const 次链 = [
  ["/断档跳变", "断档跳变"],
  ["/旁置簿", "旁置簿"],
  ["/台参", "台参"],
  ["/链见证", "链见证核证"],
];

export default function App() {
  return (
    <div className="壳">
      <aside className="轨">
        <div>
          <div className="牌名">日镜账</div>
          <div className="牌骨">日终抽取 → 周期快照 → 流水回放 → 断档跳变 → 差额清单</div>
        </div>
        <nav>
          {主链.map(([to, l]) => (
            <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "亮" : "")}>
              {l}
            </NavLink>
          ))}
          {次链.map(([to, l]) => (
            <NavLink key={to} to={to} className={({ isActive }) => (isActive ? "亮 次" : "次")}>
              {l}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="主">
        <Routes>
          <Route path="/" element={<台面 />} />
          <Route path="/账户册" element={<账户册 />} />
          <Route path="/变动流水" element={<变动流水 />} />
          <Route path="/日终抽取" element={<日终抽取 />} />
          <Route path="/周期快照" element={<周期快照 />} />
          <Route path="/回放核对" element={<回放核对 />} />
          <Route path="/连环守恒" element={<连环守恒 />} />
          <Route path="/差额清单" element={<差额清单 />} />
          <Route path="/断档跳变" element={<断档跳变 />} />
          <Route path="/旁置簿" element={<旁置簿 />} />
          <Route path="/台参" element={<台参 />} />
          <Route path="/链见证" element={<核证链见证 />} />
        </Routes>
      </main>
    </div>
  );
}
