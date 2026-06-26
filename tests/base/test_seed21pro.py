import seed21pro
import seedcore
from seed21pro import Seed21ProClient, VisionResult
from seed21pro.client import _build_input, _extract_text


def test_mock_default_response():
    client = Seed21ProClient()
    assert client.use_mock is True
    res = client.understand("你看见了什么？", image_urls=["https://x/y.png"])
    assert res.mocked is True
    assert isinstance(res, VisionResult)
    assert "你看见了什么" in res.text


def test_mock_handler_receives_images():
    def handler(text, image_urls, meta):
        return f"{len(image_urls)} imgs: {text}"

    client = Seed21ProClient(mock_handler=handler)
    res = client.understand("desc", image_urls=["a", "b"])
    assert res.text == "2 imgs: desc"


def test_build_input_shape():
    inp = _build_input("你看见了什么？", ["https://x/img.png"])
    assert inp[0]["role"] == "user"
    types = [b["type"] for b in inp[0]["content"]]
    assert types == ["input_image", "input_text"]
    assert inp[0]["content"][0]["image_url"] == "https://x/img.png"


def test_build_input_text_only():
    inp = _build_input("只有文字", [])
    assert [b["type"] for b in inp[0]["content"]] == ["input_text"]


def test_extract_text_from_output_array():
    data = {"output": [{"content": [{"type": "output_text", "text": "看到一口井"}]}]}
    assert _extract_text(data) == "看到一口井"
    assert _extract_text({"output_text": "便捷字段"}) == "便捷字段"


def test_understand_records_vision_span():
    client = Seed21ProClient()
    with seedcore.trace.start_trace("t") as t:
        with t.span("parent") as p:
            client.understand("描述这张图", image_urls=["https://x/y.png"], trace_span=p)


def test_get_client_singleton():
    c1 = seed21pro.get_client(reload=True)
    assert c1 is seed21pro.get_client()
