"""把一局对话跑成「可控、可观察」的会话。

引擎/底座是同步阻塞，对话循环跑在后台线程；事件经线程安全队列桥接给 WS 协程，
WS 收到的控制指令进 WsController。供 server/ws.py 使用，也可单测。
"""
from __future__ import annotations

import queue
import threading
from typing import Any, Dict, List, Optional

import seedcore

from .orchestrator import Controller, Orchestrator
from .role import Role
from .store import get_persona


class WsController(Controller):
    """线程安全的控制器：暂停/继续/停止/指定发言/插旁白。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._resume = threading.Event()
        self._resume.set()  # 初始非暂停
        self._stop = False
        self._next_speaker: Optional[str] = None
        self._injections: List[str] = []

    # --- 控制指令（WS 协程线程调用） ---
    def pause(self) -> None:
        self._resume.clear()

    def resume(self) -> None:
        self._resume.set()

    def stop(self) -> None:
        self._stop = True
        self._resume.set()  # 解除可能的暂停阻塞，让循环醒来退出

    def force_speaker(self, role_id: str) -> None:
        with self._lock:
            self._next_speaker = role_id

    def inject(self, text: str) -> None:
        with self._lock:
            self._injections.append(text)

    @property
    def paused(self) -> bool:
        return not self._resume.is_set()

    # --- Controller 接口（引擎线程调用） ---
    def wait_if_paused(self) -> None:
        # 带超时轮询，保证 stop 能及时唤醒
        while not self._resume.wait(timeout=0.2):
            if self._stop:
                return

    def should_stop(self) -> bool:
        return self._stop

    def next_speaker_override(self) -> Optional[str]:
        with self._lock:
            nxt, self._next_speaker = self._next_speaker, None
            return nxt

    def drain_injections(self) -> List[str]:
        with self._lock:
            items, self._injections = self._injections, []
            return items


def build_roles(role_ids: List[str], client=None, characters_dir=None) -> List[Role]:
    client = client or seedcore.get_client()
    roles = []
    for rid in role_ids:
        persona = get_persona(rid, characters_dir) if characters_dir else get_persona(rid)
        roles.append(Role(persona, client=client))
    return roles


def run_session_in_thread(
    config: Dict[str, Any],
    out_queue: "queue.Queue",
    controller: WsController,
    *,
    client=None,
    characters_dir=None,
) -> threading.Thread:
    """后台线程跑一局；事件 emit 到 out_queue（结束/异常也入队）。返回线程对象。"""

    def _emit(event: Dict[str, Any]) -> None:
        out_queue.put(event)

    def _run() -> None:
        try:
            roles = build_roles(config["roles"], client=client, characters_dir=characters_dir)
            orch = Orchestrator(
                roles,
                scene=config.get("scene", ""),
                max_rounds=config.get("max_rounds", None),
            )
            orch.run(emit=_emit, controller=controller)
        except Exception as exc:  # noqa: BLE001 - 兜底，保证前端收到错误
            out_queue.put({"type": "error", "msg": f"{type(exc).__name__}: {exc}"})

    thread = threading.Thread(target=_run, name="textgame-session", daemon=True)
    thread.start()
    return thread
