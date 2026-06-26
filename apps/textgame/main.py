"""跑一局多 agent 文游对话。

可任意方式运行：
    python -m apps.textgame.main          # 包方式
    python apps/textgame/main.py          # 直接运行该文件（含 PyCharm 运行按钮）

无真实方舟 key 时自动用 demo mock 跑通；trace 会落到 traces/<trace_id>.jsonl。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 直接以脚本方式运行时（非 -m），把仓库根目录加进 sys.path，让绝对导入可用。
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import seedcore

from apps.textgame.mock import demo_mock_handler
from apps.textgame.orchestrator import Orchestrator
from apps.textgame.role import load_roles

SCENE = "三名冒险者在暮色森林深处，发现了一口传说中的古井。"
CHARACTERS_DIR = Path(__file__).parent / "characters"


def main() -> None:
    client = seedcore.get_client()
    if client.use_mock:
        client.set_mock_handler(demo_mock_handler)
        print("（未配置真实方舟 key，使用 mock 模式运行）\n")

    # 关掉逐 span 的控制台日志，让对话流清爽；trace 仍完整落到 JSONL。
    seedcore.get_config().trace.console = False

    roles = load_roles(CHARACTERS_DIR, client=client)
    print("登场角色：" + "、".join(f"{r.name}({r.id})" for r in roles))
    print(f"【场景】{SCENE}")
    print("（对话将持续进行，按 Ctrl+C 结束）\n")

    # max_rounds=None：永不自动结束，每轮即时打印。
    game = Orchestrator(roles, scene=SCENE, max_rounds=None)
    result = game.run(on_turn=lambda t: print(f"[第{t.round}轮] {t.speaker_name}：{t.text}", flush=True))

    if result.trace_path:
        print(f"\n共 {len(result.turns)} 轮。Trace 已落地：{result.trace_path}")


if __name__ == "__main__":
    main()
