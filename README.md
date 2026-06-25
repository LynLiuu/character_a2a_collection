# Seed Character 测试工程

火山方舟 seed 模型的测试工程。**底座 (`seedcore`) 当 SDK 用**，上层每个测试工程基于它搭建。

设计文档见 [`docs/DESIGN.md`](docs/DESIGN.md)。

## 结构

```
seedcore/          底座 SDK：Client(方舟调用) / Config(全局配置) / Trace(埋点)
config/            全局配置（key、ep、默认参数、trace 开关）
apps/textgame/     上层第一个测试：多 agent 文游（自由抢麦）
tests/base/        底座测试（mock 网络）
tests/apps/        上层测试
traces/            trace JSONL 落地（gitignore）
```

## 配置方舟 key / ep

编辑 `config/config.yaml`（已 gitignore，从 `config.example.yaml` 复制）：

```yaml
ark:
  api_key: "你的真实 key"        # 或用环境变量 ARK_API_KEY 覆盖
  endpoints:
    seed-default: "ep-xxxxxxxx"   # 逻辑名 -> 方舟 endpoint id
```

> key 或默认 ep 仍是占位值时，client 自动走 **mock**，无需真实 key 即可端到端跑通。
> 真实调用需安装方舟 SDK：`pip install volcengine-python-sdk`。

## 跑起来

```bash
pip install -r requirements.txt          # 或仅 pip install pyyaml pytest
python -m apps.textgame.main             # 跑一局多 agent 文游
pytest -m base                           # 只测底座
pytest -m apps                           # 只测上层
pytest                                   # 全部
```

## 把底座当 SDK 用

```python
import seedcore
from seedcore import Message

client = seedcore.get_client()
with seedcore.trace.start_trace("my-app") as t:
    with t.span("step") as s:
        res = client.chat([Message("user", "你好")], model="seed-default", trace_span=s)
        print(res.content)
```

每次 `chat` 自动产生 `llm.call` span 并挂到当前 trace 下，落地到 `traces/<trace_id>.jsonl`。
