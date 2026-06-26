"""seedream —— 火山方舟 seedream 文生图底座 SDK（与 seedcore 平级）。

复用 seedcore 的全局配置与 trace，只负责文生图调用：

    import seedream
    client = seedream.get_client()
    res = client.generate("夜色森林中的一口古井，电影质感")
    print(res.url)

Mock 模式（占位 key / SEEDCORE_MOCK=1）下返回可渲染的占位图地址，无真实 key 也能端到端跑通。
"""
from __future__ import annotations

from .client import DEFAULT_MODEL, SeedreamClient, get_client
from .types import ImageResult

__all__ = [
    "SeedreamClient",
    "get_client",
    "ImageResult",
    "DEFAULT_MODEL",
]
