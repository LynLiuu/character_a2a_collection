"""Seedcore —— seed character 工程的底座 SDK。

上层工程把它当 SDK 用，只需：

    import seedcore
    client = seedcore.get_client()
    with seedcore.trace.start_trace("my-app") as t:
        result = client.chat([{"role": "user", "content": "hi"}])

底座只负责三件事：Client（方舟调用）/ Config（全局配置）/ Trace（埋点）。
Agent / 角色 / 编排逻辑由上层工程实现。
"""
from __future__ import annotations

from . import trace
from .client import ArkClient, get_client
from .config import Config, get_config, is_mock
from .types import ChatResult, Message

__all__ = [
    "trace",
    "ArkClient",
    "get_client",
    "Config",
    "get_config",
    "is_mock",
    "ChatResult",
    "Message",
]
