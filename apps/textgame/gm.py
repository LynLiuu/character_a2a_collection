"""旁白导演（GM）：给这局多人对话提供「外部驱动力」。

为什么需要它：纯粹的「角色抢麦→角色发言」闭环没有事件源，多 agent 会收敛成原地斗嘴。
GM 不扮演任何角色，只在固定节奏（开局 + 每隔几轮）以第三人称抛出一个外部事件/
转折/后果（如「古井深处传来回声，水面浮起一只苍白的手」），写进公共历史，逼角色去反应。

与背景导演不同：GM 必须**同步内联**在对话循环里跑——旁白要先落进 history，
角色当轮 bid/speak 才能据此反应。一次轻量 chat，慢一点也只多几百毫秒。
"""
from __future__ import annotations

from typing import List, Optional

import seedcore
from seedcore import Message

# 开局先抛一个引子，之后每隔几轮再推一把。
NARRATE_EVERY = 3
# 喂给 GM 的最近对话条数（含场景在 history[0]）。
RECENT_WINDOW = 8

_SYSTEM = (
    "你是一场多人文字冒险游戏的旁白（Game Master）。"
    "你不扮演任何角色，也不替角色说话，只以冷静的第三人称描述「外部世界此刻发生了什么」。"
    "你的职责是推动剧情：抛出新的事件、转折或角色行动的后果，制造必须被回应的钩子，"
    "让故事不停留在原地。"
)


class Narrator:
    """按节奏产出推动剧情的旁白。无状态，节奏由 round 号决定。"""

    def __init__(
        self,
        scene: str,
        *,
        client: Optional["seedcore.ArkClient"] = None,
        narrate_every: int = NARRATE_EVERY,
        recent_window: int = RECENT_WINDOW,
    ) -> None:
        self.scene = (scene or "").strip()
        self.client = client or seedcore.get_client()
        self.narrate_every = max(1, narrate_every)
        self.recent_window = max(1, recent_window)

    def should_fire(self, rnd: int) -> bool:
        """开局（第 1 轮）先来一段引子，之后每隔 narrate_every 轮推进一次。"""
        return rnd >= 1 and (rnd - 1) % self.narrate_every == 0

    def narrate(self, history: List[str], rnd: int, trace_span=None) -> str:
        """产出一句推动剧情的旁白（外部事件/转折/后果）。失败返回空串。"""
        recent = history[-self.recent_window :] if history else []
        recent_block = "\n".join(recent) if recent else "（故事刚刚开始，尚无对话）"
        is_open = rnd <= 1 or not any(not l.startswith("【") for l in recent)
        ask = (
            "现在为这个冒险开个头：用一两句话把众人此刻所处的处境推到一个需要立刻行动的当口。"
            if is_open
            else "基于以上进展，抛出一个**新的外部事件 / 转折 / 上一步行动带来的后果**，"
            "把剧情往前推一步。不要复述已经发生的事，要给出新信息或新变化。"
        )
        user = (
            f"【场景】{self.scene or '未指定'}\n\n"
            f"【目前的进展】\n{recent_block}\n\n"
            f"{ask}\n"
            "要求：第三人称客观描述，聚焦环境/事件/后果；不要替任何角色说话或下决定；"
            "具体可感（声音、光线、动作的结果），制造一个必须被回应的钩子；"
            "只输出旁白本身，不要引号、不要解释，控制在两句以内。"
        )
        result = self.client.chat(
            [Message("system", _SYSTEM), Message("user", user)],
            max_tokens=160,
            trace_span=trace_span,
            meta={"phase": "gm", "round": rnd},
        )
        return result.content.strip()
