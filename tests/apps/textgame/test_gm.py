from pathlib import Path

import seedcore
from apps.textgame.gm import Narrator
from apps.textgame.mock import demo_mock_handler
from apps.textgame.orchestrator import Orchestrator
from apps.textgame.role import load_roles

CHARS = Path(__file__).resolve().parents[3] / "apps" / "textgame" / "characters"


def _client():
    return seedcore.get_client(reload=True, mock_handler=demo_mock_handler)


def test_should_fire_rhythm():
    n = Narrator("森林", client=_client(), narrate_every=3)
    fired = [r for r in range(1, 11) if n.should_fire(r)]
    assert fired == [1, 4, 7, 10]  # 开局 + 每隔 3 轮


def test_narrate_returns_text():
    n = Narrator("暮色森林古井", client=_client())
    text = n.narrate(history=["【场景】暮色森林古井"], rnd=1)
    assert isinstance(text, str) and text


def test_orchestrator_emits_gm_narration_at_expected_rounds():
    client = _client()
    roles = load_roles(CHARS, client=client)
    narrator = Narrator("森林探险", client=client, narrate_every=3)
    events = []
    Orchestrator(roles, scene="森林探险", max_rounds=5, narrator=narrator).run(
        emit=events.append
    )
    gm_rounds = [e["round"] for e in events if e["type"] == "narration" and e.get("source") == "gm"]
    assert gm_rounds == [1, 4]  # 5 轮内开局 + 第 4 轮


def test_no_narrator_means_no_gm_narration():
    roles = load_roles(CHARS, client=_client())
    events = []
    Orchestrator(roles, scene="s", max_rounds=3).run(emit=events.append)
    assert not [e for e in events if e["type"] == "narration" and e.get("source") == "gm"]


def test_gm_narration_enters_history_before_speak():
    # GM 旁白必须先入 history，角色当轮 speak 时能看到它。
    seen_history = {}

    def spy_handler(messages, meta):
        if meta.get("phase") == "speak" and meta.get("round") == 1:
            seen_history["r1"] = "\n".join(m.content for m in messages)
        return demo_mock_handler(messages, meta)

    client = seedcore.get_client(reload=True, mock_handler=spy_handler)
    roles = load_roles(CHARS, client=client)
    narrator = Narrator("森林", client=client)
    Orchestrator(roles, scene="森林", max_rounds=1, narrator=narrator).run(emit=lambda e: None)
    assert "【旁白】" in seen_history.get("r1", "")
