"""测试全局配置：强制 mock，把 trace 落到临时目录，按路径自动打 marker。"""
import os

import pytest

# 测试期间强制 mock，绝不触网。
os.environ.setdefault("SEEDCORE_MOCK", "1")


@pytest.fixture(autouse=True)
def _isolate_trace(tmp_path, monkeypatch):
    """每个测试把 trace 落到独立临时目录，不污染仓库 traces/。"""
    monkeypatch.setenv("SEEDCORE_TRACE_DIR", str(tmp_path / "traces"))
    # 配置是单例，改 env 后需 reload 生效
    import seedcore.config as cfg

    cfg.get_config(reload=True)
    yield
    cfg.get_config(reload=True)


def pytest_collection_modifyitems(config, items):
    for item in items:
        path = str(item.fspath).replace(os.sep, "/")
        if "/tests/base/" in path:
            item.add_marker(pytest.mark.base)
        elif "/tests/apps/" in path:
            item.add_marker(pytest.mark.apps)
