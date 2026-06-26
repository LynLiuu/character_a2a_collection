"""火山方舟 seed 模型调用封装。

- 上层只用「逻辑模型名」(如 "seed-default")，内部映射到方舟 endpoint id (ep-xxxx)。
- 每次调用自动落 trace（挂到传入的 trace_span 或当前活跃 span）。
- Mock 模式：占位 key 或 SEEDCORE_MOCK=1 时返回可预测响应，
  没有真实 key 也能端到端跑通（含 trace、上层文游）。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from . import trace
from .config import Config, get_config, is_mock
from .types import ChatResult, Message, MessageLike, normalize_messages

# mock handler: (messages, meta) -> content 文本
MockHandler = Callable[[List[Message], Dict[str, Any]], str]


class ArkClient:
    def __init__(self, config: Optional[Config] = None, mock_handler: Optional[MockHandler] = None) -> None:
        self.config = config or get_config()
        self._mock_handler = mock_handler

    def set_mock_handler(self, handler: MockHandler) -> "ArkClient":
        self._mock_handler = handler
        return self

    @property
    def use_mock(self) -> bool:
        return is_mock(self.config)

    def _resolve_endpoint(self, model: str) -> str:
        # 逻辑名 -> ep；找不到则按已是 ep 处理
        return self.config.ark.endpoints.get(model, model)

    def chat(
        self,
        messages: List[MessageLike],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[str] = None,  # "json" -> json_object
        trace_span: Optional[trace.Span] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> ChatResult:
        model = model or self.config.defaults.model
        endpoint = self._resolve_endpoint(model)
        temperature = self.config.defaults.temperature if temperature is None else temperature
        max_tokens = self.config.defaults.max_tokens if max_tokens is None else max_tokens
        msgs = normalize_messages(messages)
        meta = meta or {}

        parent = trace_span if trace_span is not None else trace.current_span()
        if parent is None:
            parent = trace.NOOP

        with parent.span(
            "llm.call",
            model=model,
            endpoint=endpoint,
            mock=self.use_mock,
        ) as span:
            span.set(
                msg_count=len(msgs),
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
            if meta:
                span.set(**{f"meta.{k}": v for k, v in meta.items()})

            t0 = time.time()
            if self.use_mock:
                content = self._mock_call(msgs, meta)
                result = ChatResult(content=content, model=model, mocked=True)
            else:
                result = self._real_call(endpoint, msgs, temperature, max_tokens, response_format, model)

            span.set(
                latency_ms=round((time.time() - t0) * 1000, 2),
                completion_chars=len(result.content),
            )
            if result.usage:
                span.set(usage=result.usage)
            return result

    # ------------------------------------------------------------------ #
    def _mock_call(self, messages: List[Message], meta: Dict[str, Any]) -> str:
        if self._mock_handler is not None:
            return self._mock_handler(messages, meta)
        last = messages[-1].content if messages else ""
        return f"[mock] {last[:60]}"

    def _real_call(
        self,
        endpoint: str,
        messages: List[Message],
        temperature: float,
        max_tokens: int,
        response_format: Optional[str],
        model: str,
    ) -> ChatResult:
        # 方舟 OpenAI 兼容 REST：POST {base_url}/chat/completions
        url = self.config.ark.base_url.rstrip("/") + "/chat/completions"
        payload: Dict[str, Any] = {
            "model": endpoint,  # 可传 ep-xxxx 或模型名
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

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
            raise RuntimeError(f"方舟 API 错误 {e.code}: {detail}") from e

        content = data["choices"][0]["message"].get("content") or ""
        return ChatResult(content=content, model=model, usage=data.get("usage"), raw=data)


_client_singleton: Optional[ArkClient] = None


def get_client(reload: bool = False, mock_handler: Optional[MockHandler] = None) -> ArkClient:
    global _client_singleton
    if _client_singleton is None or reload:
        _client_singleton = ArkClient(mock_handler=mock_handler)
    elif mock_handler is not None:
        _client_singleton.set_mock_handler(mock_handler)
    return _client_singleton
