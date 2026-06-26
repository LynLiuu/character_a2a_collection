import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import apps.textgame.store as store
from apps.textgame.server.app import app

CHARS = Path(__file__).resolve().parents[3] / "apps" / "textgame" / "characters"


@pytest.fixture
def client(tmp_path, monkeypatch):
    # 把人设卡目录指向临时副本，避免污染真实文件
    d = tmp_path / "characters"
    shutil.copytree(CHARS, d)
    monkeypatch.setattr(store, "CHARACTERS_DIR", d)
    return TestClient(app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_list_characters(client):
    r = client.get("/api/characters")
    assert r.status_code == 200
    ids = {c["id"] for c in r.json()}
    assert {"alice", "bob", "cara"} <= ids
    alice = next(c for c in r.json() if c["id"] == "alice")
    assert "探险家" in alice["persona"] and alice["avatar"] == "🗺️"


def test_create_update_delete_character(client, tmp_path):
    # create
    r = client.post("/api/characters", json={
        "id": "dora", "name": "多拉", "persona": "向导", "avatar": "🧭", "assertiveness": 0.6,
    })
    assert r.status_code == 201, r.text
    assert (tmp_path / "characters" / "dora.yaml").exists()
    assert (tmp_path / "characters" / "dora.md").exists()

    # duplicate create -> 400
    assert client.post("/api/characters", json={"id": "dora", "name": "x"}).status_code == 400

    # update
    r = client.put("/api/characters/dora", json={"id": "ignored", "name": "多拉", "persona": "改了"})
    assert r.status_code == 200 and "改了" in r.json()["persona"]

    # delete
    assert client.delete("/api/characters/dora").status_code == 204
    assert client.get("/api/characters/dora").status_code == 404


def test_websocket_full_game_and_records(client):
    with client.websocket_connect("/ws/session") as wsconn:
        wsconn.send_json({"type": "start", "roles": ["alice", "bob", "cara"], "scene": "测试", "max_rounds": 2})
        sid = None
        types = []
        ended = None
        for _ in range(200):
            ev = wsconn.receive_json()
            types.append(ev["type"])
            if ev["type"] == "session":
                sid = ev["id"]
            if ev["type"] == "ended":
                ended = ev
                break
        assert sid and ended and ended["total_turns"] == 2
        assert {"round_start", "pick", "turn", "round_end"} <= set(types)

    # 会话已落盘，REST 可取对话 / trace / 时延
    rec = client.get(f"/api/sessions/{sid}").json()
    assert rec["total_turns"] == 2 and len(rec["turns"]) == 2

    tree = client.get(f"/api/sessions/{sid}/trace").json()["tree"]
    assert tree and tree[0]["name"] == "textgame"

    lat = client.get(f"/api/sessions/{sid}/latency").json()
    assert lat["round_count"] == 2 and lat["llm"]["count"] >= 1
