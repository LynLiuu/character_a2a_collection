"""seedream 文生图返回类型。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class ImageResult:
    """一次文生图调用的结果。urls 为生成图片的访问地址列表。"""

    urls: List[str]
    model: str
    size: str = ""
    usage: Optional[dict] = None
    raw: Optional[Any] = None
    mocked: bool = False

    @property
    def url(self) -> Optional[str]:
        return self.urls[0] if self.urls else None
