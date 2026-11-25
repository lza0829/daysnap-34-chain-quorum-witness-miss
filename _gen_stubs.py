
from pathlib import Path

root = Path(__file__).resolve().parent / "backend" / "app" / "modules"
mods = [
    "开户首日无前日",
    "同日重复抽取幂等",
    "流水迟到补抽",
    "销户终镜",
    "负余额闸",
    "币种隔离",
    "半截抽取回滚",
    "快照封印写闸",
    "回放权威择定",
    "断档补齐",
    "断档旁置",
    "跳变阈值",
    "账户分片抽取",
    "抽取时钟漂移",
    "流水序缺口",
    "并户继承镜",
    "子户汇总镜",
    "假期跳日日历",
    "差额分桶",
    "三日连环守恒",
    "抽取重试预算",
    "跨日切点策略",
]
root.mkdir(parents=True, exist_ok=True)
(root / "__init__.py").write_text("", encoding="utf-8")
for m in mods:
    d = root / m
    d.mkdir(parents=True, exist_ok=True)
    (d / "__init__.py").write_text(
        f'"""空桩 · {m}。邻题扩展点，主链冒烟不依赖本模块。"""\n\n启用 = False\n\n\ndef 说明():\n    return "{m}"\n',
        encoding="utf-8",
    )
print("modules", len(mods))
