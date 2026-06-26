"""角色 = 人设 + 记忆 + 基于底座 client 的发言能力。

Role 不感知方舟/ep，只用 seedcore 的 client 与 trace。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

import seedcore
from seedcore import Message


DEFAULT_AVATAR = "🎭"
DEFAULT_COLOR = "#8b8b8b"


@dataclass
class Persona:
    """一张人设卡 = 结构化字段(yaml) + Markdown 人设正文({id}.md)。"""

    id: str
    name: str
    persona: str  # Markdown 正文，来自 {id}.md（缺省回退 yaml 的 persona 字段）
    goals: List[str] = field(default_factory=list)
    speaking_style: str = ""
    assertiveness: float = 0.5
    avatar: str = DEFAULT_AVATAR
    color: str = DEFAULT_COLOR

    @classmethod
    def load(cls, path: Path) -> "Persona":
        """path 指向 {id}.yaml；同名 {id}.md 存在则作为人设正文。"""
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        md_path = path.with_suffix(".md")
        if md_path.exists():
            persona = md_path.read_text(encoding="utf-8").strip()
        else:
            persona = (data.get("persona") or "").strip()
        return cls(
            id=data["id"],
            name=data["name"],
            persona=persona,
            goals=list(data.get("goals", [])),
            speaking_style=data.get("speaking_style", ""),
            assertiveness=float(data.get("assertiveness", 0.5)),
            avatar=data.get("avatar", DEFAULT_AVATAR),
            color=data.get("color", DEFAULT_COLOR),
        )

    def to_meta(self) -> Dict[str, Any]:
        """结构化字段（不含正文），用于写 yaml / API 列表。"""
        return {
            "id": self.id,
            "name": self.name,
            "avatar": self.avatar,
            "color": self.color,
            "goals": list(self.goals),
            "speaking_style": self.speaking_style,
            "assertiveness": self.assertiveness,
        }

    def to_dict(self) -> Dict[str, Any]:
        """完整卡片（含正文），用于 API 单卡返回。"""
        return {**self.to_meta(), "persona": self.persona}

    def save(self, characters_dir: Path) -> None:
        """写回磁盘：{id}.yaml(元信息) + {id}.md(正文)。"""
        characters_dir = Path(characters_dir)
        characters_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = characters_dir / f"{self.id}.yaml"
        md_path = characters_dir / f"{self.id}.md"
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(self.to_meta(), f, allow_unicode=True, sort_keys=False)
        md_path.write_text(self.persona.strip() + "\n", encoding="utf-8")


@dataclass
class Bid:
    eagerness: float  # 0~10
    intent: str


class Role:
    def __init__(self, persona: Persona, client: Optional[seedcore.ArkClient] = None) -> None:
        self.persona = persona
        self.client = client or seedcore.get_client()
        self.rounds_since_spoke = 0  # 防饿死计数

    @property
    def id(self) -> str:
        return self.persona.id

    @property
    def name(self) -> str:
        return self.persona.name

    def _system_prompt(self) -> str:
        p = self.persona
        parts = [p.persona]
        if p.goals:
            parts.append("你的目标：\n" + "\n".join(f"- {g}" for g in p.goals))
        if p.speaking_style:
            parts.append(f"说话风格：{p.speaking_style}")
        parts.append(f"你是「{p.name}」，请始终保持人设，用第一人称发言，不要旁白。")
        return "\n\n".join(parts)

    def _history_block(self, history: List[str]) -> str:
        if not history:
            return "（对话刚刚开始）"
        return "\n".join(history)

    def bid(self, history: List[str], rnd: int, trace_span=None) -> Bid:
        """抢麦：给出本轮发言意愿(0~10)和一句话意图。"""
        sys = self._system_prompt()
        user = (
            "这是当前的公共对话记录：\n"
            f"{self._history_block(history)}\n\n"
            "现在轮到决定谁发言。基于你的人设和目标，你此刻有多想发言？\n"
            "严格只输出一行 JSON，不要任何其它文字：\n"
            "{\"eagerness\": 0到10的数字, \"intent\": \"你想说什么的一句话概括\"}"
        )
        # 注：seed-character 模型不支持 response_format=json_object，靠提示词 + 宽松解析。
        result = self.client.chat(
            [Message("system", sys), Message("user", user)],
            max_tokens=120,
            trace_span=trace_span,
            meta={"phase": "bid", "role": self.id, "round": rnd},
        )
        return self._parse_bid(result.content)

    def _parse_bid(self, content: str) -> Bid:
        eagerness, intent = 5.0, ""  # 解析失败兜底：中等意愿
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                eagerness = float(data.get("eagerness", 5))
                intent = str(data.get("intent", "")).strip()
            except (ValueError, TypeError, json.JSONDecodeError):
                pass
        eagerness = max(0.0, min(10.0, eagerness))
        return Bid(eagerness=eagerness, intent=intent)

    def speak(self, history: List[str], rnd: int, trace_span=None) -> str:
        """真正发言，生成一句台词。"""
        sys = self._system_prompt()
        user = (
            "这是当前的公共对话记录：\n"
            f"{self._history_block(history)}\n\n"
            "现在轮到你发言，说一句符合你人设、推动剧情的话。"
            "只输出台词本身，不要带名字前缀。不要试图结束对话，让剧情继续发展下去。"
        )
        result = self.client.chat(
            [Message("system", sys), Message("user", user)],
            trace_span=trace_span,
            meta={"phase": "speak", "role": self.id, "round": rnd},
        )
        return result.content.strip()


def load_roles(characters_dir: Path, client: Optional[seedcore.ArkClient] = None) -> List[Role]:
    characters_dir = Path(characters_dir)
    roles: List[Role] = []
    for path in sorted(characters_dir.glob("*.yaml")):
        roles.append(Role(Persona.load(path), client=client))
    return roles
