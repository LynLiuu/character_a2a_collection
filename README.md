# Seed Character 测试工程

火山方舟 seed 模型的测试工程。**底座 (`seedcore`) 当 SDK 用**，上层每个测试工程基于它搭建。

设计文档见 [`docs/DESIGN.md`](docs/DESIGN.md)。

## 结构

```
seedcore/          底座 SDK：Client(方舟调用) / Config(全局配置) / Trace(埋点)
config/            全局配置（key、ep、默认参数、trace 开关）
apps/textgame/     上层第一个测试：多 agent 文游（引擎 + server + frontend，自包含）
tests/base/        底座测试（mock 网络）
tests/apps/        上层测试
```

> 每个上层 app 自包含：引擎、后端、前端、运行产物(traces/sessions) 都在自己目录下，
> 底座只当 SDK 被 import，互不耦合。

## 配置方舟 key / ep

编辑 `config/config.yaml`（已 gitignore，从 `config.example.yaml` 复制）：

```yaml
ark:
  api_key: "你的真实 key"        # 或用环境变量 ARK_API_KEY 覆盖
  endpoints:
    seed-default: "ep-xxxxxxxx"   # 逻辑名 -> 方舟 endpoint id
```

> key 或默认 ep 仍是占位值时，client 自动走 **mock**，无需真实 key 即可端到端跑通。
> 真实调用走方舟 OpenAI 兼容 REST 接口（标准库 `urllib`，无需额外 SDK）。
> 注：`seed-character` 模型不支持 `response_format=json_object`，抢麦的 JSON 靠提示词 + 宽松解析。

## 跑起来

```bash
pip install -r requirements.txt          # 或仅 pip install pyyaml pytest
python -m apps.textgame.main             # 跑一局多 agent 文游（命令行）
pytest -m base                           # 只测底座
pytest -m apps                           # 只测上层
pytest                                   # 全部
```

## Web 应用（多 agent 文游可视化）

前后端分离：FastAPI 后端(`apps/textgame/server`) + React/Vite/Tailwind 前端(`apps/textgame/frontend`)。
主交互页三栏（角色栏 / 对话流 / Trace·时延·历史），可暂停/继续/停止、指定下一发言者、插旁白，人设卡在线编辑写回磁盘。

开发模式（前端 :5173 代理到后端 :8000，热更新）：

```bash
pip install -r requirements.txt                       # fastapi/uvicorn 已含
uvicorn apps.textgame.server.app:app --reload         # 后端 :8000
cd apps/textgame/frontend && npm install && npm run dev   # 前端 :5173
```

一体化模式（构建后单端口）：

```bash
cd apps/textgame/frontend && npm install && npm run build # 产出 apps/textgame/frontend/dist
uvicorn apps.textgame.server.app:app                  # 后端直接托管前端，访问 :8000
```

> 无真实 key/ep 时仍自动 mock（可设 `SEEDCORE_MOCK=1` 强制），前端可完整体验。
> 对话记录落盘 `apps/textgame/sessions/{id}.json`，trace 落盘 `apps/textgame/traces/{trace_id}.jsonl`，均已 gitignore。

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

每次 `chat` 自动产生 `llm.call` span 并挂到当前 trace 下，落地到配置的 trace 目录（默认 `traces/`，可经 `config.trace.dir` 或 `SEEDCORE_TRACE_DIR` 覆盖；textgame 自身已重定向到 `apps/textgame/traces/`）。
