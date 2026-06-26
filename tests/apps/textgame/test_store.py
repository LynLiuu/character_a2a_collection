import shutil
from pathlib import Path

import pytest

from apps.textgame import store
from apps.textgame.role import Persona

CHARS = Path(__file__).resolve().parents[3] / "apps" / "textgame" / "characters"


def test_load_reads_md_as_persona():
    p = Persona.load(CHARS / "alice.yaml")
    assert p.id == "alice"
    assert p.avatar == "🗺️"
    assert p.color == "#e25555"
    # 正文来自 alice.md
    assert "探险家" in p.persona


def test_list_personas():
    ps = store.list_personas(CHARS)
    ids = [p.id for p in ps]
    assert {"alice", "bob", "cara"} <= set(ids)


@pytest.fixture
def tmp_chars(tmp_path):
    d = tmp_path / "characters"
    shutil.copytree(CHARS, d)
    return d


def test_upsert_creates_yaml_and_md(tmp_chars):
    p = store.upsert_persona(
        {"id": "dora", "name": "多拉", "persona": "# 多拉\n探险向导", "avatar": "🧭", "assertiveness": 0.6},
        directory=tmp_chars,
        must_be_new=True,
    )
    assert (tmp_chars / "dora.yaml").exists()
    assert (tmp_chars / "dora.md").exists()
    reloaded = store.get_persona("dora", tmp_chars)
    assert reloaded.name == "多拉"
    assert "探险向导" in reloaded.persona
    assert reloaded.avatar == "🧭"


def test_upsert_update_existing_persists(tmp_chars):
    store.upsert_persona({"id": "alice", "name": "爱丽丝", "persona": "改写后的人设"}, directory=tmp_chars, must_exist=True)
    assert "改写后的人设" in store.get_persona("alice", tmp_chars).persona


def test_delete_removes_both_files(tmp_chars):
    store.delete_persona("cara", tmp_chars)
    assert not (tmp_chars / "cara.yaml").exists()
    assert not (tmp_chars / "cara.md").exists()
    with pytest.raises(store.CardError):
        store.get_persona("cara", tmp_chars)


def test_invalid_id_rejected(tmp_chars):
    with pytest.raises(store.CardError):
        store.upsert_persona({"id": "../evil", "name": "x"}, directory=tmp_chars)
    with pytest.raises(store.CardError):
        store.upsert_persona({"id": "Bad Id", "name": "x"}, directory=tmp_chars)


def test_must_be_new_rejects_duplicate(tmp_chars):
    with pytest.raises(store.CardError):
        store.upsert_persona({"id": "alice", "name": "x"}, directory=tmp_chars, must_be_new=True)
