"""seed21pro 多模态视觉理解返回类型。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class VisionResult:
    """一次视觉理解调用的结果。text 为模型对图片/文本的理解输出。"""

    text: str
    model: str
    usage: Optional[dict] = None
    raw: Optional[Any] = None
    mocked: bool = False
