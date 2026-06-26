import seedream
import seedcore
from seedream import ImageResult, SeedreamClient


def test_mock_default_returns_placeholder_url():
    client = SeedreamClient()
    assert client.use_mock is True
    res = client.generate("夜色森林中的一口古井")
    assert res.mocked is True
    assert isinstance(res, ImageResult)
    assert res.url and res.url.startswith("http")


def test_mock_handler_used():
    def handler(prompt, meta):
        return f"https://example.com/{meta.get('tag')}.png"

    client = SeedreamClient(mock_handler=handler)
    res = client.generate("x", meta={"tag": "bg"})
    assert res.url == "https://example.com/bg.png"


def test_endpoint_resolution():
    client = SeedreamClient()
    # seedream 逻辑名映射到配置里的 ep；未知名按 ep 透传
    assert client._resolve_endpoint("seedream") == client.config.ark.endpoints["seedream"]
    assert client._resolve_endpoint("ep-raw-1") == "ep-raw-1"


def test_generate_records_image_span():
    client = SeedreamClient()
    with seedcore.trace.start_trace("t") as t:
        with t.span("parent") as p:
            client.generate("一座城堡", trace_span=p)
    # span 正常结束即视为埋点成功


def test_get_client_singleton_and_handler_swap():
    c1 = seedream.get_client(reload=True)
    c2 = seedream.get_client()
    assert c1 is c2
    seedream.get_client(mock_handler=lambda prompt, meta: "https://x/y.png")
    assert c2.generate("z").url == "https://x/y.png"
