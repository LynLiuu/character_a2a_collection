"""seed21pro —— 火山方舟 seed-2.1-pro 多模态视觉理解底座 SDK（与 seedcore 平级）。

复用 seedcore 的全局配置与 trace，走 Responses API 看图+文做理解/推理：

    import seed21pro
    client = seed21pro.get_client()
    res = client.understand("你看见了什么？", image_urls=["https://.../img.png"])
    print(res.text)

也可纯文本调用（不传 image_urls）。Mock 模式下返回可预测文本，无真实 key 也能端到端跑通。
"""
from __future__ import annotations

from .client import DEFAULT_MODEL, Seed21ProClient, get_client
from .types import VisionResult

__all__ = [
    "Seed21ProClient",
    "get_client",
    "VisionResult",
    "DEFAULT_MODEL",
]
