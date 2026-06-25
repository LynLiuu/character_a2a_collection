"""自研轻量 trace。

模型（参考 OpenTelemetry 但零外部依赖）：
  - Trace：一次完整运行（如一局文游对话），有 trace_id。
  - Span：trace 下一段操作，有 span_id/parent_id/name/start/end/attributes/status/events。

用法：
    with trace.start_trace("textgame") as t:
        with t.span("game.round", round=1) as rs:
            with rs.span("role.bid", role="alice") as bs:
                client.chat(..., trace_span=bs)   # llm.call 会挂到 bs 下

也支持自动挂载：未显式传 trace_span 时，client 会挂到「当前 span」(contextvar)。

后端可替换：写入走 TraceSink 接口，本期实现 JsonlSink + ConsoleSink，
以后换 OTel/Langfuse 只需新增 sink。
"""
from __future__ import annotations

import contextvars
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import get_config

_current_span: "contextvars.ContextVar[Optional[Span]]" = contextvars.ContextVar(
    "seedcore_current_span", default=None
)


# --------------------------------------------------------------------------- #
# Sinks
# --------------------------------------------------------------------------- #
class TraceSink:
    def write(self, record: Dict[str, Any]) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class JsonlSink(TraceSink):
    def __init__(self, directory: str, trace_id: str) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / f"{trace_id}.jsonl"

    @property
    def path(self) -> Path:
        return self._path

    def write(self, record: Dict[str, Any]) -> None:
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


class ConsoleSink(TraceSink):
    def write(self, record: Dict[str, Any]) -> None:
        indent = "  " * record.get("depth", 0)
        dur = record.get("duration_ms")
        dur_s = f" {dur}ms" if dur is not None else ""
        status = "" if record.get("status") == "ok" else f" [{record.get('status')}]"
        attrs = {
            k: v
            for k, v in record.get("attributes", {}).items()
            if k not in ("error",)
        }
        attr_s = " " + json.dumps(attrs, ensure_ascii=False) if attrs else ""
        print(f"{indent}· {record['name']}{dur_s}{status}{attr_s}")


# --------------------------------------------------------------------------- #
# Span
# --------------------------------------------------------------------------- #
class Span:
    def __init__(
        self,
        name: str,
        trace_id: str,
        parent_id: Optional[str],
        depth: int,
        sinks: List[TraceSink],
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.name = name
        self.trace_id = trace_id
        self.span_id = uuid.uuid4().hex[:16]
        self.parent_id = parent_id
        self.depth = depth
        self.attributes: Dict[str, Any] = dict(attributes or {})
        self.events: List[Dict[str, Any]] = []
        self.status = "ok"
        self.start: Optional[float] = None
        self.end: Optional[float] = None
        self._sinks = sinks
        self._token = None

    def set(self, **attrs: Any) -> "Span":
        self.attributes.update(attrs)
        return self

    def event(self, name: str, **attrs: Any) -> "Span":
        self.events.append({"name": name, "ts": time.time(), "attrs": attrs})
        return self

    def span(self, name: str, **attrs: Any) -> "Span":
        return Span(
            name,
            trace_id=self.trace_id,
            parent_id=self.span_id,
            depth=self.depth + 1,
            sinks=self._sinks,
            attributes=attrs,
        )

    def __enter__(self) -> "Span":
        self.start = time.time()
        self._token = _current_span.set(self)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.end = time.time()
        if exc_type is not None:
            self.status = "error"
            self.set(error=f"{exc_type.__name__}: {exc}")
        if self._token is not None:
            _current_span.reset(self._token)
            self._token = None
        for sink in self._sinks:
            sink.write(self.to_record())
        return False

    def to_record(self) -> Dict[str, Any]:
        dur = None
        if self.start is not None and self.end is not None:
            dur = round((self.end - self.start) * 1000, 2)
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "name": self.name,
            "start": self.start,
            "end": self.end,
            "duration_ms": dur,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
        }


class _NoopSpan(Span):
    """当 trace 关闭或没有活跃 trace 时使用，所有操作无副作用。"""

    def __init__(self) -> None:
        super().__init__("noop", trace_id="noop", parent_id=None, depth=0, sinks=[])

    def span(self, name: str, **attrs: Any) -> "Span":
        return self

    def __enter__(self) -> "Span":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


NOOP = _NoopSpan()


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
def _build_sinks(trace_id: str) -> List[TraceSink]:
    cfg = get_config().trace
    if not cfg.enabled:
        return []
    sinks: List[TraceSink] = [JsonlSink(cfg.dir, trace_id)]
    if cfg.console:
        sinks.append(ConsoleSink())
    return sinks


def start_trace(name: str, **attrs: Any) -> Span:
    """开启一次新的 trace，返回根 span（用作上下文管理器）。"""
    cfg = get_config().trace
    if not cfg.enabled:
        return NOOP
    trace_id = uuid.uuid4().hex
    return Span(
        name,
        trace_id=trace_id,
        parent_id=None,
        depth=0,
        sinks=_build_sinks(trace_id),
        attributes=attrs,
    )


def current_span() -> Optional[Span]:
    return _current_span.get()


def trace_path(span: Span) -> Optional[str]:
    """返回该 trace 的 JSONL 落地路径（若有 JsonlSink）。"""
    for sink in span._sinks:  # noqa: SLF001 - 内部工具函数
        if isinstance(sink, JsonlSink):
            return str(sink.path)
    return None
