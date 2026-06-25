import seedcore
from seedcore.config import is_mock, load_config


def test_loads_example_config():
    cfg = seedcore.get_config(reload=True)
    assert cfg.ark.base_url
    assert "seed-default" in cfg.ark.endpoints
    assert cfg.defaults.model == "seed-default"


def test_env_override_api_key(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "real-key-123")
    cfg = load_config()
    assert cfg.ark.api_key == "real-key-123"


def test_is_mock_on_placeholder():
    cfg = seedcore.get_config(reload=True)
    assert is_mock(cfg) is True


def test_is_mock_false_with_real_key_and_endpoint(monkeypatch):
    monkeypatch.delenv("SEEDCORE_MOCK", raising=False)
    monkeypatch.setenv("ARK_API_KEY", "real-key-123")
    cfg = load_config()
    cfg.ark.endpoints[cfg.defaults.model] = "ep-real-endpoint"  # 配齐真实 ep
    assert is_mock(cfg) is False


def test_is_mock_true_when_endpoint_placeholder(monkeypatch):
    monkeypatch.delenv("SEEDCORE_MOCK", raising=False)
    monkeypatch.setenv("ARK_API_KEY", "real-key-123")
    cfg = load_config()  # 端点仍是占位
    assert is_mock(cfg) is True
