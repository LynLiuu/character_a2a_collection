from pathlib import Path

import seedcore
from apps.textgame.mock import demo_mock_handler
from apps.textgame.role import Persona, Role, load_roles

CHARS = Path(__file__).resolve().parents[3] / "apps" / "textgame" / "characters"


def test_persona_load():
    p = Persona.load(CHARS / "alice.yaml")
    assert p.id == "alice"
    assert p.name == "爱丽丝"
    assert p.assertiveness == 0.8
    assert p.goals


def test_load_roles_sorted():
    roles = load_roles(CHARS)
    ids = [r.id for r in roles]
    assert ids == sorted(ids)
    assert "alice" in ids and "bob" in ids


def test_bid_parses_json_from_mock():
    client = seedcore.get_client(reload=True, mock_handler=demo_mock_handler)
    role = Role(Persona.load(CHARS / "alice.yaml"), client=client)
    bid = role.bid(history=["【场景】测试"], rnd=1)
    assert 0 <= bid.eagerness <= 10
    assert bid.intent


def test_bid_fallback_on_bad_json():
    client = seedcore.get_client(reload=True, mock_handler=lambda m, meta: "not json")
    role = Role(Persona.load(CHARS / "bob.yaml"), client=client)
    bid = role.bid(history=[], rnd=1)
    assert bid.eagerness == 5.0  # 兜底中等意愿


def test_speak_returns_text():
    client = seedcore.get_client(reload=True, mock_handler=demo_mock_handler)
    role = Role(Persona.load(CHARS / "alice.yaml"), client=client)
    text = role.speak(history=[], rnd=1)
    assert isinstance(text, str) and text
