import seedcore
from seedcore import ArkClient, Message


def test_mock_default_response():
    client = ArkClient()
    assert client.use_mock is True
    res = client.chat([Message("user", "你好世界")])
    assert res.mocked is True
    assert "你好世界" in res.content


def test_mock_handler_used():
    def handler(messages, meta):
        return f"handled:{meta.get('phase')}"

    client = ArkClient(mock_handler=handler)
    res = client.chat([Message("user", "hi")], meta={"phase": "bid"})
    assert res.content == "handled:bid"


def test_endpoint_resolution():
    client = ArkClient()
    # 逻辑名映射到配置里的 ep（占位值），未知名按 ep 透传
    assert client._resolve_endpoint("seed-default") == client.config.ark.endpoints["seed-default"]
    assert client._resolve_endpoint("ep-raw-123") == "ep-raw-123"


def test_chat_records_llm_span():
    client = ArkClient()
    with seedcore.trace.start_trace("t") as t:
        with t.span("parent") as p:
            client.chat([Message("user", "x")], trace_span=p)
    # span 正常结束即视为埋点成功（详细落地在 trace 测试中验证）
