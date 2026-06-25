"""多 agent 文游：不同 agent 对应不同角色，各自读取自己的人设，自由抢麦推进对话。

这是建立在 seedcore 底座之上的第一个上层测试工程。
"""
from __future__ import annotations

from .orchestrator import GameResult, Orchestrator, Turn
from .role import Persona, Role, load_roles

__all__ = ["Orchestrator", "GameResult", "Turn", "Role", "Persona", "load_roles"]
