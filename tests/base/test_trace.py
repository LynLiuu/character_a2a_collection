import json
from pathlib import Path

import seedcore
from seedcore import trace


def _read_records(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def test_nested_spans_and_jsonl():
    with trace.start_trace("root") as t:
        with t.span("child", foo="bar") as c:
            with c.span("grandchild"):
                pass
        path = trace.trace_path(t)

    records = _read_records(path)
    names = [r["name"] for r in records]
    # 子 span 先结束先写入
    assert names == ["grandchild", "child", "root"]

    by_name = {r["name"]: r for r in records}
    assert by_name["child"]["attributes"]["foo"] == "bar"
    assert by_name["grandchild"]["parent_id"] == by_name["child"]["span_id"]
    assert by_name["child"]["parent_id"] == by_name["root"]["span_id"]
    assert by_name["root"]["parent_id"] is None
    assert by_name["grandchild"]["depth"] == 2


def test_current_span_autoattach():
    with trace.start_trace("root") as t:
        with t.span("a") as a:
            assert trace.current_span() is a
        assert trace.current_span() is t


def test_error_status_recorded():
    try:
        with trace.start_trace("root") as t:
            path = trace.trace_path(t)
            with t.span("boom"):
                raise ValueError("kaboom")
    except ValueError:
        pass
    records = _read_records(path)
    boom = next(r for r in records if r["name"] == "boom")
    assert boom["status"] == "error"
    assert "kaboom" in boom["attributes"]["error"]


def test_disabled_trace_is_noop(monkeypatch):
    monkeypatch.setenv("SEEDCORE_TRACE_DIR", "traces")
    import seedcore.config as cfg

    c = cfg.get_config(reload=True)
    c.trace.enabled = False
    span = trace.start_trace("root")
    assert span is trace.NOOP
    with span as t:
        with t.span("x"):
            pass  # 不应抛错、不应落盘
