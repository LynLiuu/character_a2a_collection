import queue
import time
from pathlib import Path

import seedcore
from apps.textgame.mock import demo_mock_handler
from apps.textgame.orchestrator import Controller, Orchestrator
from apps.textgame.role import load_roles
from apps.textgame.session import WsController, run_session_in_thread

CHARS = Path(__file__).resolve().parents[3] / "apps" / "textgame" / "characters"


def _roles():
    client = seedcore.get_client(reload=True, mock_handler=demo_mock_handler)
    return load_roles(CHARS, client=client)


def test_emit_event_stream_shape():
    events = []
    Orchestrator(_roles(), scene="s", max_rounds=2).run(emit=events.append)
    types = [e["type"] for e in events]
    assert types[0] == "round_start"
    assert "bid" in types and "pick" in types and "turn" in types and "round_end" in types
    assert types[-1] == "ended"
    ended = events[-1]
    assert ended["reason"] == "max_rounds" and ended["total_turns"] == 2


def test_force_speaker_override():
    class ForceBob(Controller):
        def __init__(self):
            self.used = False

        def next_speaker_override(self):
            if not self.used:
                self.used = True
                return "bob"
            return None

    events = []
    Orchestrator(_roles(), max_rounds=1).run(emit=events.append, controller=ForceBob())
    pick = next(e for e in events if e["type"] == "pick")
    assert pick["winner"] == "bob" and pick["forced"] is True
    # 强制发言时跳过 bid
    assert not any(e["type"] == "bid" for e in events)


def test_inject_narration():
    class InjectOnce(Controller):
        def __init__(self):
            self.done = False

        def drain_injections(self):
            if not self.done:
                self.done = True
                return ["远处传来狼嚎。"]
            return []

    events = []
    Orchestrator(_roles(), max_rounds=1).run(emit=events.append, controller=InjectOnce())
    narr = next(e for e in events if e["type"] == "narration")
    assert "狼嚎" in narr["text"]


def test_ws_controller_stop_ends_thread():
    seedcore.get_client(reload=True, mock_handler=demo_mock_handler)
    out: queue.Queue = queue.Queue()
    ctrl = WsController()
    thread = run_session_in_thread(
        {"roles": ["alice", "bob", "cara"], "scene": "s", "max_rounds": None},  # 无限轮
        out,
        ctrl,
        characters_dir=CHARS,
    )
    # 收到至少一轮后请求停止
    seen_turn = False
    deadline = time.time() + 5
    while time.time() < deadline:
        ev = out.get(timeout=5)
        if ev["type"] == "turn":
            seen_turn = True
            ctrl.stop()
        if ev["type"] == "ended":
            assert ev["reason"] == "stopped"
            break
    thread.join(timeout=5)
    assert seen_turn and not thread.is_alive()
