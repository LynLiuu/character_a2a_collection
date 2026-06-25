"""跑一局多 agent 文游对话。

    python -m apps.textgame.main

无真实方舟 key 时自动用 demo mock 跑通；trace 会落到 traces/<trace_id>.jsonl。
"""
from __future__ import annotations

from pathlib import Path

import seedcore

from .mock import demo_mock_handler
from .orchestrator import Orchestrator
from .role import load_roles

SCENE = "三名冒险者在暮色森林深处，发现了一口传说中的古井。"
CHARACTERS_DIR = Path(__file__).parent / "characters"


def main() -> None:
    client = seedcore.get_client()
    if client.use_mock:
        client.set_mock_handler(demo_mock_handler)
        print("（未配置真实方舟 key，使用 mock 模式运行）\n")

    roles = load_roles(CHARACTERS_DIR, client=client)
    print("登场角色：" + "、".join(f"{r.name}({r.id})" for r in roles) + "\n")

    game = Orchestrator(roles, scene=SCENE, max_rounds=8)
    result = game.run()

    print("\n===== 对话回放 =====")
    print(f"【场景】{SCENE}\n")
    for turn in result.turns:
        print(f"[第{turn.round}轮] {turn.speaker_name}：{turn.text}")

    if result.trace_path:
        print(f"\nTrace 已落地：{result.trace_path}")


if __name__ == "__main__":
    main()
