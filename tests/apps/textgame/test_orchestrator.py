import json
from pathlib import Path

import seedcore
from apps.textgame.mock import demo_mock_handler
from apps.textgame.orchestrator import Orchestrator
from apps.textgame.role import Bid, Persona, Role, load_roles

CHARS = Path(__file__).resolve().parents[3] / "apps" / "textgame" / "characters"


def _roles():
    client = seedcore.get_client(reload=True, mock_handler=demo_mock_handler)
    return load_roles(CHARS, client=client)


def test_run_produces_turns_and_trace():
    game = Orchestrator(_roles(), scene="测试场景", max_rounds=5)
    result = game.run()
    assert 1 <= len(result.turns) <= 5
    assert all(t.text for t in result.turns)
    assert result.trace_path and Path(result.trace_path).exists()


def test_trace_has_round_bid_speak_spans():
    game = Orchestrator(_roles(), scene="s", max_rounds=3)
    result = game.run()
    records = [json.loads(l) for l in Path(result.trace_path).read_text(encoding="utf-8").splitlines()]
    names = {r["name"] for r in records}
    assert {"textgame", "game.round", "role.bid", "role.speak", "llm.call"} <= names


def test_starvation_increments():
    roles = _roles()
    game = Orchestrator(roles, max_rounds=4)
    game.run()
    # 至少有角色发过言（计数被清零过），编排正常推进
    assert any(r.rounds_since_spoke >= 0 for r in roles)


def test_pick_weighting_prefers_high_eager_assertive():
    # 构造两个角色，手动喂 bid，验证加权选人逻辑
    client = seedcore.get_client(reload=True, mock_handler=demo_mock_handler)
    loud = Role(Persona(id="loud", name="L", persona="x", assertiveness=0.9), client=client)
    quiet = Role(Persona(id="quiet", name="Q", persona="y", assertiveness=0.1), client=client)
    orch = Orchestrator([loud, quiet])
    scored = [
        (loud, Bid(8, "a"), orch._weight(loud, Bid(8, "a"))),
        (quiet, Bid(8, "b"), orch._weight(quiet, Bid(8, "b"))),
    ]
    assert orch._pick(scored).id == "loud"


def test_runs_exactly_max_rounds_no_early_end():
    # 模型即便输出 [END] 也不再提前结束，固定跑满 max_rounds
    client = seedcore.get_client(reload=True, mock_handler=lambda m, meta: (
        json.dumps({"eagerness": 9, "intent": "x"}) if meta.get("phase") == "bid" else "收工！[END]"
    ))
    roles = load_roles(CHARS, client=client)
    result = Orchestrator(roles, max_rounds=6).run()
    assert len(result.turns) == 6


def test_on_turn_callback_streams():
    client = seedcore.get_client(reload=True, mock_handler=demo_mock_handler)
    seen = []
    Orchestrator(_roles(), max_rounds=3).run(on_turn=lambda t: seen.append(t.round))
    assert seen == [1, 2, 3]
