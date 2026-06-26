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

import time
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
    latency_ms: Optional[float] = None


@dataclass
class GameResult:
    turns: List[Turn]
    trace_path: Optional[str]
    reason: str = "max_rounds"


class Controller:
    """运行控制接口，默认全部 no-op（即原始无干预行为）。

    WebSocket 服务端会用 WsController 实现这些方法，注入暂停/停止/指定发言/插旁白。
    """

    def wait_if_paused(self) -> None:
        return None

    def should_stop(self) -> bool:
        return False

    def next_speaker_override(self) -> Optional[str]:
        """返回被指定的发言者 id（消费一次），无则 None。"""
        return None

    def drain_injections(self) -> List[str]:
        """取出待插入的旁白文本（取走即清空）。"""
        return []


_NO_CONTROLLER = Controller()


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

    def _role_by_id(self, rid: str) -> Optional[Role]:
        for r in self.roles:
            if r.id == rid:
                return r
        return None

    def _bump_starvation(self, winner: Role) -> None:
        for role in self.roles:
            role.rounds_since_spoke = 0 if role.id == winner.id else role.rounds_since_spoke + 1

    def run(
        self,
        on_turn: Optional[Callable[[Turn], None]] = None,
        emit: Optional[Callable[[dict], None]] = None,
        controller: Optional[Controller] = None,
    ) -> GameResult:
        """跑一局对话。

        max_rounds=None 时无限循环、永不自动结束。
        on_turn：每产生一轮发言回调一次（向后兼容）。
        emit(event)：把过程拆成结构化事件流（round_start/bid/pick/turn/narration/round_end/ended/error）。
        controller：注入暂停/停止/指定发言/插旁白；默认无干预（同原行为）。
        """
        emit = emit or (lambda e: None)
        controller = controller or _NO_CONTROLLER
        turns: List[Turn] = []
        history: List[str] = []
        if self.scene:
            history.append(f"【场景】{self.scene}")

        reason = "max_rounds"
        with seedcore.trace.start_trace(
            "textgame",
            roles=[r.id for r in self.roles],
            max_rounds=self.max_rounds,
        ) as t:
            trace_path = seedcore.trace.trace_path(t)
            try:
                rnd = 0
                while self.max_rounds is None or rnd < self.max_rounds:
                    controller.wait_if_paused()
                    if controller.should_stop():
                        reason = "stopped"
                        break

                    # 旁白插入（不占发言轮）
                    for text in controller.drain_injections():
                        history.append(f"【旁白】{text}")
                        emit({"type": "narration", "round": rnd, "text": text})

                    rnd += 1
                    round_t0 = time.time()
                    emit({"type": "round_start", "round": rnd})
                    with t.span("game.round", round=rnd) as round_span:
                        override = controller.next_speaker_override()
                        forced = override is not None and self._role_by_id(override) is not None

                        if forced:
                            winner = self._role_by_id(override)
                        else:
                            scored = []
                            for role in self.roles:
                                with round_span.span("role.bid", role=role.id) as bid_span:
                                    bid = role.bid(history, rnd, trace_span=bid_span)
                                    weight = self._weight(role, bid)
                                    bid_span.set(eagerness=bid.eagerness, weight=round(weight, 2))
                                    scored.append((role, bid, weight))
                                    emit({
                                        "type": "bid", "round": rnd, "role": role.id,
                                        "eagerness": bid.eagerness, "intent": bid.intent,
                                        "weight": round(weight, 2),
                                    })
                            winner = self._pick(scored)

                        round_span.set(winner=winner.id, forced=forced)
                        emit({"type": "pick", "round": rnd, "winner": winner.id, "forced": forced})

                        speak_t0 = time.time()
                        with round_span.span("role.speak", role=winner.id) as speak_span:
                            text = winner.speak(history, rnd, trace_span=speak_span)
                            speak_span.set(chars=len(text))
                        latency_ms = round((time.time() - speak_t0) * 1000, 2)

                        history.append(f"{winner.name}：{text}")
                        turn = Turn(rnd, winner.id, winner.name, text, latency_ms=latency_ms)
                        turns.append(turn)
                        if on_turn is not None:
                            on_turn(turn)
                        emit({
                            "type": "turn", "round": rnd, "role": winner.id,
                            "name": winner.name, "text": text, "latency_ms": latency_ms,
                        })

                        self._bump_starvation(winner)
                    emit({"type": "round_end", "round": rnd,
                          "duration_ms": round((time.time() - round_t0) * 1000, 2)})
            except KeyboardInterrupt:
                reason = "interrupted"
                t.set(interrupted=True)

        emit({"type": "ended", "reason": reason, "total_turns": len(turns), "trace_path": trace_path})
        return GameResult(turns=turns, trace_path=trace_path, reason=reason)
