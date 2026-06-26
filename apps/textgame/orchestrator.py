"""自由抢麦编排器。

每一轮 (game.round span)：
  1. Bid 阶段 (role.bid span)：每个角色给出发言意愿(0~10)+意图。
  2. 加权选人：score = eagerness * (0.5 + assertiveness) + 防饿死加成。
     - 防饿死：连续 N 轮没发言的角色获得 starvation_bonus * N 的加成。
     - 平手时按「最久没发言」再按角色顺序决定，保证可复现（不引入随机）。
  3. Speak 阶段 (role.speak span)：胜者生成完整发言，写入公共历史。
终止：达到 max_rounds（设为 None 则无限轮、永不自动结束）或 Ctrl+C。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

import seedcore

from .role import Bid, Role


@dataclass
class Turn:
    round: int
    speaker_id: str
    speaker_name: str
    text: str


@dataclass
class GameResult:
    turns: List[Turn]
    trace_path: Optional[str]


class Orchestrator:
    def __init__(
        self,
        roles: List[Role],
        scene: str = "",
        max_rounds: Optional[int] = 8,  # None = 无限轮，永不自动结束
        starvation_bonus: float = 1.5,
    ) -> None:
        if not roles:
            raise ValueError("至少需要一个角色")
        self.roles = roles
        self.scene = scene.strip()
        self.max_rounds = max_rounds
        self.starvation_bonus = starvation_bonus

    def _weight(self, role: Role, bid: Bid) -> float:
        base = bid.eagerness * (0.5 + role.persona.assertiveness)
        return base + self.starvation_bonus * role.rounds_since_spoke

    def _pick(self, scored: List[tuple]) -> Role:
        # scored: (role, bid, weight)；按 (weight, rounds_since_spoke) 降序，再按顺序稳定
        best = max(
            scored,
            key=lambda x: (x[2], x[0].rounds_since_spoke),
        )
        return best[0]

    def run(self, on_turn: Optional[Callable[[Turn], None]] = None) -> GameResult:
        """跑一局对话。

        max_rounds=None 时无限循环、永不自动结束（Ctrl+C 优雅停止）。
        on_turn：每产生一轮发言就回调一次，用于实时流式打印。
        """
        turns: List[Turn] = []
        history: List[str] = []
        if self.scene:
            history.append(f"【场景】{self.scene}")

        with seedcore.trace.start_trace(
            "textgame",
            roles=[r.id for r in self.roles],
            max_rounds=self.max_rounds,
        ) as t:
            trace_path = seedcore.trace.trace_path(t)
            try:
                rnd = 0
                while self.max_rounds is None or rnd < self.max_rounds:
                    rnd += 1
                    with t.span("game.round", round=rnd) as round_span:
                        scored = []
                        for role in self.roles:
                            with round_span.span("role.bid", role=role.id) as bid_span:
                                bid = role.bid(history, rnd, trace_span=bid_span)
                                weight = self._weight(role, bid)
                                bid_span.set(eagerness=bid.eagerness, weight=round(weight, 2))
                                scored.append((role, bid, weight))

                        winner = self._pick(scored)
                        round_span.set(winner=winner.id)

                        with round_span.span("role.speak", role=winner.id) as speak_span:
                            text = winner.speak(history, rnd, trace_span=speak_span)
                            speak_span.set(chars=len(text))

                        history.append(f"{winner.name}：{text}")
                        turn = Turn(round=rnd, speaker_id=winner.id, speaker_name=winner.name, text=text)
                        turns.append(turn)
                        if on_turn is not None:
                            on_turn(turn)

                        # 更新防饿死计数
                        for role in self.roles:
                            if role.id == winner.id:
                                role.rounds_since_spoke = 0
                            else:
                                role.rounds_since_spoke += 1
            except KeyboardInterrupt:
                t.set(interrupted=True)

        return GameResult(turns=turns, trace_path=trace_path)
