"""全局配置加载。

加载顺序：
  1. 环境变量 SEEDCORE_CONFIG 指定的路径
  2. <repo>/config/config.yaml
  3. <repo>/config/config.example.yaml（兜底，保证开箱即跑）

单字段可被环境变量覆盖（ARK_API_KEY / ARK_BASE_URL / SEEDCORE_TRACE_DIR / SEEDCORE_MOCK）。
本期方舟 key/ep 只预留占位值；占位时 client 自动走 mock。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import yaml

PLACEHOLDER_PREFIX = "PLACEHOLDER"


@dataclass
class ArkConfig:
    api_key: str
    base_url: str
    endpoints: Dict[str, str] = field(default_factory=dict)


@dataclass
class Defaults:
    model: str = "seed-default"
    temperature: float = 0.8
    max_tokens: int = 1024
    timeout_s: int = 30


@dataclass
class TraceConfig:
    enabled: bool = True
    dir: str = "traces"
    console: bool = True


@dataclass
class Config:
    ark: ArkConfig
    defaults: Defaults
    trace: TraceConfig
    source_path: Optional[str] = None


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _config_path() -> Path:
    env = os.environ.get("SEEDCORE_CONFIG")
    if env:
        return Path(env)
    root = project_root()
    real = root / "config" / "config.yaml"
    if real.exists():
        return real
    return root / "config" / "config.example.yaml"


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(path: Optional[Path] = None) -> Config:
    path = path or _config_path()
    data = _load_yaml(path)

    ark_d = data.get("ark", {})
    api_key = os.environ.get("ARK_API_KEY", ark_d.get("api_key", f"{PLACEHOLDER_PREFIX}_ARK_API_KEY"))
    base_url = os.environ.get("ARK_BASE_URL", ark_d.get("base_url", ""))
    ark = ArkConfig(api_key=api_key, base_url=base_url, endpoints=dict(ark_d.get("endpoints", {})))

    def_d = data.get("defaults", {})
    defaults = Defaults(
        model=def_d.get("model", "seed-default"),
        temperature=float(def_d.get("temperature", 0.8)),
        max_tokens=int(def_d.get("max_tokens", 1024)),
        timeout_s=int(def_d.get("timeout_s", 30)),
    )

    tr_d = data.get("trace", {})
    trace = TraceConfig(
        enabled=bool(tr_d.get("enabled", True)),
        dir=os.environ.get("SEEDCORE_TRACE_DIR", tr_d.get("dir", "traces")),
        console=bool(tr_d.get("console", True)),
    )

    return Config(ark=ark, defaults=defaults, trace=trace, source_path=str(path))


_singleton: Optional[Config] = None


def get_config(reload: bool = False) -> Config:
    global _singleton
    if _singleton is None or reload:
        _singleton = load_config()
    return _singleton


def is_mock(config: Optional[Config] = None) -> bool:
    """以下任一情况走 mock：显式 SEEDCORE_MOCK / 占位(或空) key / 默认模型的 ep 未配置。"""
    if os.environ.get("SEEDCORE_MOCK", "").lower() in ("1", "true", "yes"):
        return True
    config = config or get_config()
    key = config.ark.api_key or ""
    if key.startswith(PLACEHOLDER_PREFIX) or key == "":
        return True
    ep = config.ark.endpoints.get(config.defaults.model, "")
    return (not ep) or ep.startswith(PLACEHOLDER_PREFIX)
