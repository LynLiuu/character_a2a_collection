"""火山方舟 seedream 文生图调用封装。

与 seedcore 平级的独立底座 SDK，但复用 seedcore 的：
  - Config（同一 ARK_API_KEY / base_url / endpoints 映射）
  - Trace（每次生成自动落 image.gen span，挂到当前活跃 span 或传入的 trace_span）

调用方舟 REST：POST {base_url}/images/generations（与 chat/completions 不同的端点）。
Mock 模式：占位 key 或 SEEDCORE_MOCK=1 时返回可预测的占位图地址，无真实 key 也能端到端跑通。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from seedcore import trace
from seedcore.config import Config, get_config, is_mock

from .types import ImageResult

DEFAULT_MODEL = "seedream"

# mock handler: (prompt, meta) -> 图片 url
MockHandler = Callable[[str, Dict[str, Any]], str]


def _placeholder_url(prompt: str) -> str:
    """mock 模式下返回一个可渲染的占位图地址（按 prompt 生成）。"""
    q = urllib.parse.quote(prompt[:200])
    return (
        "https://copilot-cn.bytedance.net/api/ide/v1/text_to_image"
        f"?prompt={q}&image_size=landscape_16_9"
    )


class SeedreamClient:
    def __init__(self, config: Optional[Config] = None, mock_handler: Optional[MockHandler] = None) -> None:
        self.config = config or get_config()
        self._mock_handler = mock_handler

    def set_mock_handler(self, handler: MockHandler) -> "SeedreamClient":
        self._mock_handler = handler
        return self

    @property
    def use_mock(self) -> bool:
        return is_mock(self.config)

    def _resolve_endpoint(self, model: str) -> str:
        return self.config.ark.endpoints.get(model, model)

    def generate(
        self,
        prompt: str,
        *,
        model: str = DEFAULT_MODEL,
        size: str = "2K",
        watermark: bool = True,
        sequential_image_generation: str = "disabled",
        trace_span: Optional[trace.Span] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> ImageResult:
        endpoint = self._resolve_endpoint(model)
        meta = meta or {}

        parent = trace_span if trace_span is not None else trace.current_span()
        if parent is None:
            parent = trace.NOOP

        with parent.span(
            "image.gen",
            model=model,
            endpoint=endpoint,
            mock=self.use_mock,
        ) as span:
            span.set(size=size, prompt_chars=len(prompt))
            if meta:
                span.set(**{f"meta.{k}": v for k, v in meta.items()})

            t0 = time.time()
            if self.use_mock:
                url = self._mock_call(prompt, meta)
                result = ImageResult(urls=[url], model=model, size=size, mocked=True)
            else:
                result = self._real_call(endpoint, prompt, size, watermark, sequential_image_generation, model)

            span.set(
                latency_ms=round((time.time() - t0) * 1000, 2),
                image_count=len(result.urls),
            )
            return result

    # ------------------------------------------------------------------ #
    def _mock_call(self, prompt: str, meta: Dict[str, Any]) -> str:
        if self._mock_handler is not None:
            return self._mock_handler(prompt, meta)
        return _placeholder_url(prompt)

    def _real_call(
        self,
        endpoint: str,
        prompt: str,
        size: str,
        watermark: bool,
        sequential_image_generation: str,
        model: str,
    ) -> ImageResult:
        url = self.config.ark.base_url.rstrip("/") + "/images/generations"
        payload: Dict[str, Any] = {
            "model": endpoint,
            "prompt": prompt,
            "sequential_image_generation": sequential_image_generation,
            "response_format": "url",
            "size": size,
            "stream": False,
            "watermark": watermark,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.ark.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.defaults.timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            raise RuntimeError(f"seedream API 错误 {e.code}: {detail}") from e

        urls: List[str] = [item.get("url", "") for item in data.get("data", []) if item.get("url")]
        return ImageResult(urls=urls, model=model, size=size, usage=data.get("usage"), raw=data)


_client_singleton: Optional[SeedreamClient] = None


def get_client(reload: bool = False, mock_handler: Optional[MockHandler] = None) -> SeedreamClient:
    global _client_singleton
    if _client_singleton is None or reload:
        _client_singleton = SeedreamClient(mock_handler=mock_handler)
    elif mock_handler is not None:
        _client_singleton.set_mock_handler(mock_handler)
    return _client_singleton
