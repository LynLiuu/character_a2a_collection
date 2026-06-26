"""火山方舟 seed-2.1-pro 多模态视觉理解调用封装。

与 seedcore 平级的独立底座 SDK，复用 seedcore 的 Config 与 Trace。
走方舟 Responses API：POST {base_url}/responses，输入是 input_image / input_text 的内容块。

典型用途：给模型看一张图（或几张）+ 一段提问，让它描述/推理。
本工程用它「看场景 + 最近对话」来产出 seedream 的生图提示词。

Mock 模式：占位 key 或 SEEDCORE_MOCK=1 时返回可预测文本，无真实 key 也能端到端跑通。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from seedcore import trace
from seedcore.config import Config, get_config, is_mock

from .types import VisionResult

DEFAULT_MODEL = "seed-2.1-pro"
# seed-2.1-pro 带推理，首响应较慢（实测 30s+），用独立的更大超时，避免误判超时。
DEFAULT_TIMEOUT_S = 120

# mock handler: (text, image_urls, meta) -> 输出文本
MockHandler = Callable[[str, List[str], Dict[str, Any]], str]


def _build_input(text: str, image_urls: List[str]) -> List[Dict[str, Any]]:
    content: List[Dict[str, Any]] = []
    for url in image_urls:
        content.append({"type": "input_image", "image_url": url})
    if text:
        content.append({"type": "input_text", "text": text})
    return [{"role": "user", "content": content}]


def _extract_text(data: Dict[str, Any]) -> str:
    """从 Responses API 返回里抽取文本，兼容 output_text 便捷字段与 output 数组。"""
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    parts: List[str] = []
    for item in data.get("output", []) or []:
        for block in item.get("content", []) or []:
            if block.get("type") in ("output_text", "text") and block.get("text"):
                parts.append(block["text"])
    return "".join(parts)


class Seed21ProClient:
    def __init__(self, config: Optional[Config] = None, mock_handler: Optional[MockHandler] = None) -> None:
        self.config = config or get_config()
        self._mock_handler = mock_handler

    def set_mock_handler(self, handler: MockHandler) -> "Seed21ProClient":
        self._mock_handler = handler
        return self

    @property
    def use_mock(self) -> bool:
        return is_mock(self.config)

    def _resolve_endpoint(self, model: str) -> str:
        return self.config.ark.endpoints.get(model, model)

    def understand(
        self,
        text: str,
        *,
        image_urls: Optional[List[str]] = None,
        model: str = DEFAULT_MODEL,
        trace_span: Optional[trace.Span] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> VisionResult:
        image_urls = image_urls or []
        endpoint = self._resolve_endpoint(model)
        meta = meta or {}

        parent = trace_span if trace_span is not None else trace.current_span()
        if parent is None:
            parent = trace.NOOP

        with parent.span(
            "vision.understand",
            model=model,
            endpoint=endpoint,
            mock=self.use_mock,
        ) as span:
            span.set(text_chars=len(text), image_count=len(image_urls))
            if meta:
                span.set(**{f"meta.{k}": v for k, v in meta.items()})

            t0 = time.time()
            if self.use_mock:
                out = self._mock_call(text, image_urls, meta)
                result = VisionResult(text=out, model=model, mocked=True)
            else:
                result = self._real_call(endpoint, text, image_urls, model)

            span.set(
                latency_ms=round((time.time() - t0) * 1000, 2),
                completion_chars=len(result.text),
            )
            if result.usage:
                span.set(usage=result.usage)
            return result

    # ------------------------------------------------------------------ #
    def _mock_call(self, text: str, image_urls: List[str], meta: Dict[str, Any]) -> str:
        if self._mock_handler is not None:
            return self._mock_handler(text, image_urls, meta)
        return f"[mock vision] {text[:60]}"

    def _real_call(self, endpoint: str, text: str, image_urls: List[str], model: str) -> VisionResult:
        url = self.config.ark.base_url.rstrip("/") + "/responses"
        payload: Dict[str, Any] = {
            "model": endpoint,
            "input": _build_input(text, image_urls),
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
            with urllib.request.urlopen(req, timeout=max(self.config.defaults.timeout_s, DEFAULT_TIMEOUT_S)) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            raise RuntimeError(f"seed-2.1-pro API 错误 {e.code}: {detail}") from e

        return VisionResult(text=_extract_text(data), model=model, usage=data.get("usage"), raw=data)


_client_singleton: Optional[Seed21ProClient] = None


def get_client(reload: bool = False, mock_handler: Optional[MockHandler] = None) -> Seed21ProClient:
    global _client_singleton
    if _client_singleton is None or reload:
        _client_singleton = Seed21ProClient(mock_handler=mock_handler)
    elif mock_handler is not None:
        _client_singleton.set_mock_handler(mock_handler)
    return _client_singleton
