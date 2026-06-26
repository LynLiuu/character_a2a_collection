"""人设卡的磁盘存取（list/get/upsert/delete），供 REST API 与测试复用。

每张卡 = {id}.yaml(元信息) + {id}.md(Markdown 人设正文)。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .role import DEFAULT_AVATAR, DEFAULT_COLOR, Persona

CHARACTERS_DIR = Path(__file__).parent / "characters"
_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


class CardError(Exception):
    """人设卡操作错误（非法 id、不存在、重复等）。"""


def _validate_id(cid: str) -> str:
    if not isinstance(cid, str) or not _ID_RE.match(cid):
        raise CardError(f"非法角色 id: {cid!r}（要求小写字母开头，仅含小写字母/数字/下划线）")
    return cid


def _resolve_dir(directory: Optional[Path]) -> Path:
    # 默认在调用时读取模块全局，便于测试 monkeypatch CHARACTERS_DIR
    return Path(directory) if directory is not None else CHARACTERS_DIR


def list_personas(directory: Optional[Path] = None) -> List[Persona]:
    directory = _resolve_dir(directory)
    return [Persona.load(p) for p in sorted(directory.glob("*.yaml"))]


def get_persona(cid: str, directory: Optional[Path] = None) -> Persona:
    _validate_id(cid)
    path = _resolve_dir(directory) / f"{cid}.yaml"
    if not path.exists():
        raise CardError(f"角色不存在: {cid}")
    return Persona.load(path)


def _persona_from_dict(data: Dict[str, Any]) -> Persona:
    cid = _validate_id(data.get("id", ""))
    name = (data.get("name") or "").strip()
    if not name:
        raise CardError("name 不能为空")
    return Persona(
        id=cid,
        name=name,
        persona=(data.get("persona") or "").strip(),
        goals=list(data.get("goals", []) or []),
        speaking_style=data.get("speaking_style", "") or "",
        assertiveness=float(data.get("assertiveness", 0.5)),
        avatar=data.get("avatar") or DEFAULT_AVATAR,
        color=data.get("color") or DEFAULT_COLOR,
    )


def upsert_persona(
    data: Dict[str, Any],
    directory: Optional[Path] = None,
    *,
    must_be_new: bool = False,
    must_exist: bool = False,
) -> Persona:
    directory = _resolve_dir(directory)
    persona = _persona_from_dict(data)
    path = directory / f"{persona.id}.yaml"
    if must_be_new and path.exists():
        raise CardError(f"角色已存在: {persona.id}")
    if must_exist and not path.exists():
        raise CardError(f"角色不存在: {persona.id}")
    persona.save(directory)
    return persona


def delete_persona(cid: str, directory: Optional[Path] = None) -> None:
    _validate_id(cid)
    directory = _resolve_dir(directory)
    yaml_path = directory / f"{cid}.yaml"
    if not yaml_path.exists():
        raise CardError(f"角色不存在: {cid}")
    yaml_path.unlink()
    md_path = directory / f"{cid}.md"
    if md_path.exists():
        md_path.unlink()
