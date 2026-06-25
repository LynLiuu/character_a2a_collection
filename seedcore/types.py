"""底座通用数据类型。上层只依赖这些类型，不感知方舟/ep。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union


@dataclass
class Message:
    """一条对话消息。role ∈ {system, user, assistant}。"""

    role: str
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


MessageLike = Union[Message, Dict[str, str]]


def normalize_messages(messages: List[MessageLike]) -> List[Message]:
    out: List[Message] = []
    for m in messages:
        if isinstance(m, Message):
            out.append(m)
        else:
            out.append(Message(role=m["role"], content=m["content"]))
    return out


@dataclass
class ChatResult:
    """一次模型调用的结果。"""

    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    raw: Optional[Any] = None
    mocked: bool = False
