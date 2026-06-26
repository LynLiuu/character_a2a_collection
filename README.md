# Seed Character 测试工程

火山方舟 seed 模型的测试工程。**底座 (`seedcore`) 当 SDK 用**，上层每个测试工程基于它搭建。

设计文档见 [`docs/DESIGN.md`](docs/DESIGN.md)。

## 结构

```
seedcore/          底座 SDK：Client(方舟 chat 调用) / Config(全局配置) / Trace(埋点)
seedream/          底座 SDK：文生图（方舟 images/generations）
seed21pro/         底座 SDK：seed-2.1-pro 多模态视觉理解（方舟 responses）
config/            全局配置（key、ep、默认参数、trace 开关）
apps/textgame/     上层第一个测试：多 agent 文游（引擎 + server + frontend，自包含）
tests/base/        底座测试（mock 网络）
tests/apps/        上层测试
```

> 三个底座 SDK（`seedcore` / `seedream` / `seed21pro`）平级，**共用同一份 `config/config.yaml`**
> （同一个 `ARK_API_KEY` / `base_url`，只在 `endpoints` 里加逻辑名→ep 映射）与同一套 trace。

> 每个上层 app 自包含：引擎、后端、前端、运行产物(traces/sessions) 都在自己目录下，
> 底座只当 SDK 被 import，互不耦合。

## 配置方舟 key / ep

编辑 `config/config.yaml`（已 gitignore，从 `config.example.yaml` 复制）：

```yaml
ark:
  api_key: "你的真实 key"        # 或用环境变量 ARK_API_KEY 覆盖
  endpoints:
    seed-default: "ep-xxxxxxxx"   # chat（seedcore）
    seedream: "ep-xxxxxxxx"       # 文生图（seedream）
    seed-2.1-pro: "ep-xxxxxxxx"   # 视觉理解（seed21pro）
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

前后端分离：FastAPI 后端(`apps/textgame/server`) + React/Vite/Tailwind 前端(`apps/textgame/frontend`)，简洁白色画风。
左侧角色栏 + 中央对话流，可暂停/继续/停止、指定下一发言者、插旁白，人设卡在线编辑写回磁盘。
右侧 Trace·时延·历史面板默认收起，点表头按钮展开（回看历史会话时自动展开）。

**动态背景**：对话进行时，后端 `BackgroundDirector` 异步生成与剧情同步的背景图——
seed21pro 看「场景 + 最近几条对话」产出一句文生图提示词，再交给 seedream 出图，
生成完成后经 WebSocket 推 `background` 事件，前端半透明淡入铺到对话流下层。
开局即出一张、之后每隔几轮刷新；生成全程在独立线程、单任务不堆积，
**绝不阻塞对话生成与渲染**（背景慢一点也不影响），失败也静默跳过。

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

### seedream（文生图）

```python
import seedream

client = seedream.get_client()
res = client.generate("星际穿越，黑洞，电影大片质感，oc 渲染", size="2K")
print(res.url)        # 第一张图地址；res.urls 是全部
```

走方舟 `POST /images/generations`，每次自动产生 `image.gen` span。占位 key / `SEEDCORE_MOCK=1` 时返回占位图地址。

### seed21pro（多模态视觉理解）

```python
import seed21pro

client = seed21pro.get_client()
res = client.understand(
    "你看见了什么？",
    image_urls=["https://.../some.png"],   # 可传多张，也可不传纯文本
)
print(res.text)
```

走方舟 `POST /responses`，输入是 `input_image` / `input_text` 内容块，每次自动产生 `vision.understand` span。占位 key / `SEEDCORE_MOCK=1` 时返回占位文本。

> textgame 的动态背景就是把这两个底座串起来：seed21pro 看「场景 + 最近对话」产出一句生图提示词，
> 再交给 seedream 出图，生成后半透明铺到对话流背景上（详见下文）。
