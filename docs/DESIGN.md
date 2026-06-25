# Seed Character 测试工程 — 设计文档

> 状态：**待确认**（确认后再进入开发）
> 日期：2026-06-25

## 0. 目标与原则

1. **底座 / 上层解耦**：底座是一套可被复用的 SDK，上层每个测试工程（文游、其它）都把底座当 SDK 用。
2. **底座很薄**：只做三件事 —— **Client**（火山方舟 seed 模型调用封装）、**Config**（全局配置）、**Trace**（自研轻量埋点）。Agent / 角色 / 编排逻辑**不进底座**，放在各上层工程里。
3. **配置外置**：方舟的 `api_key` 和 `endpoint(ep)` 放全局配置文件，调用时读取。本期**只预留**，不需要真实可用的 key。
4. **Trace 必须埋好**：每次模型调用、每个 agent 发言、每轮编排都进 trace，便于后面回放/分析。
5. **底座测试与上层测试分开**：`tests/base/` 与 `tests/apps/` 物理分离，pytest marker 区分。

---

## 1. 目录结构

```
test_sc/
├── seedcore/                  # ★ 底座 SDK（包名可改）
│   ├── __init__.py            # 对外导出：get_client / get_config / trace
│   ├── config.py              # 全局配置加载（方舟 key/ep、默认模型参数）
│   ├── client.py              # ArkClient：方舟 seed 模型调用封装
│   ├── trace.py               # 自研轻量 trace（trace_id / span / JSONL 落地）
│   └── types.py               # Message / ChatResult 等数据类型
│
├── config/
│   ├── config.example.yaml    # 配置模板（进 git）
│   └── config.yaml            # 真实配置（.gitignore，本期放占位值）
│
├── apps/                      # ★ 上层工程集合
│   └── textgame/              # 第一个测试：多 agent 文游
│       ├── __init__.py
│       ├── characters/        # 人设文件（每个角色一个 yaml）
│       │   ├── _schema.md     # 人设字段说明
│       │   ├── alice.yaml
│       │   └── bob.yaml
│       ├── role.py            # Role：加载人设 + 持有记忆 + 基于底座 client 发言
│       ├── orchestrator.py    # 自由抢麦编排器
│       └── main.py            # 跑一局对话的入口
│
├── tests/
│   ├── base/                  # 底座测试（mock 掉方舟网络调用）
│   │   ├── test_config.py
│   │   ├── test_client.py
│   │   └── test_trace.py
│   └── apps/
│       └── textgame/
│           ├── test_role.py
│           └── test_orchestrator.py
│
├── traces/                    # trace JSONL 落地目录（.gitignore）
├── pyproject.toml             # 依赖 + pytest marker 配置
├── requirements.txt
└── docs/DESIGN.md             # 本文件
```

---

## 2. 底座详细设计

### 2.1 Config（`seedcore/config.py`）

**全局配置文件** `config/config.yaml`（模板见 `config.example.yaml`）：

```yaml
ark:
  api_key: "PLACEHOLDER_ARK_API_KEY"      # 本期占位
  base_url: "https://ark.cn-beijing.volces.com/api/v3"
  # 逻辑模型名 -> 方舟 endpoint id，调用时按逻辑名取 ep
  endpoints:
    seed-default: "ep-xxxxxxxx-xxxxx"      # 本期占位
    seed-lite:    "ep-yyyyyyyy-yyyyy"

defaults:
  model: "seed-default"
  temperature: 0.8
  max_tokens: 1024
  timeout_s: 30

trace:
  enabled: true
  dir: "traces"
  console: true        # 是否同时打印到控制台
```

- 加载顺序：环境变量（`SEEDCORE_CONFIG` 指定路径）> `config/config.yaml` > `config.example.yaml`。
- 单个字段支持环境变量覆盖（如 `ARK_API_KEY`），方便 CI / 不落盘 key。
- 提供 `get_config()` 返回单例（dataclass，带类型）。
- **本期只预留**：占位值即可，`ArkClient` 真正发请求时若发现是占位值，可选择走 mock（见 2.2）。

### 2.2 Client（`seedcore/client.py`）

火山方舟 seed 模型 = OpenAI 兼容接口（`volcengine-python-sdk` 的 `Ark`，或直接用 openai SDK 指 base_url）。封装：

```python
class ArkClient:
    def __init__(self, config=None): ...
    def chat(
        self,
        messages: list[Message],
        *,
        model: str = "seed-default",     # 逻辑名，内部映射到 ep
        temperature: float | None = None,
        max_tokens: int | None = None,
        trace_span=None,                  # 传入则把本次调用挂到该 span 下
    ) -> ChatResult: ...

    def chat_stream(...) -> Iterator[ChatDelta]: ...  # 预留，第一版可后置
```

- 逻辑模型名 → ep 映射在底座内部完成，上层只认 `"seed-default"` 这类名字。
- **每次调用自动落 trace**：记录 model/ep、入参摘要、prompt token 估算、耗时、返回、报错。
- **Mock 模式**：当 key 为占位值或显式 `SEEDCORE_MOCK=1` 时，返回可预测的假响应，让全链路（含 trace、上层文游）在没有真实 key 时也能端到端跑通和测试。

### 2.3 Trace（`seedcore/trace.py`）—— 自研轻量

模型（参考 OTel 但极简，零外部依赖）：

- **Trace**：一次完整运行（如一局文游对话），有 `trace_id`。
- **Span**：trace 下的一段操作，有 `span_id` / `parent_id` / `name` / `start` / `end` / `attributes` / `status`。
  - span 类型示例：`llm.call`（底座产生）、`game.round`、`role.bid`、`role.speak`（上层产生）。
- 嵌套通过上下文管理器：

```python
with trace.start_trace("textgame") as t:
    with t.span("game.round", round=1) as s:
        with s.span("role.bid", role="alice") as b:
            client.chat(..., trace_span=b)   # llm.call 自动挂到 b 下
```

- **落地**：每个 span 结束写一行 JSON 到 `traces/{trace_id}.jsonl`；`console=true` 时同时输出可读的树形/缩进日志。
- 设计为**后端可替换**：写入走一个 `TraceSink` 接口，本期实现 `JsonlSink` + `ConsoleSink`，以后换 OTel/Langfuse 只加一个 sink。

### 2.4 对外导出（`seedcore/__init__.py`）

```python
from seedcore import get_client, get_config, trace
# 上层只 import 这三样
```

---

## 3. 上层：多 agent 文游（`apps/textgame/`）

### 3.1 人设文件（`characters/*.yaml`）

每个角色一个文件，角色只读自己的人设：

```yaml
id: alice
name: "爱丽丝"
persona: |
  你是爱丽丝，一个好奇心旺盛、说话直接的少女探险家……
goals:
  - 找到地图上标记的古井
speaking_style: "短句，爱用反问"
# 抢麦倾向（可选）：越主动越容易抢到发言
assertiveness: 0.7
```

`Role` 类：加载人设 → 构造 system prompt → 持有自己的对话记忆 → 调底座 `client.chat` 发言。**Role 不知道方舟/ep 的存在**，只用底座 `get_client()`。

### 3.2 编排：自由抢麦（`orchestrator.py`）

> 按你选的「自由抢麦」：没有 GM 强制点名，角色竞争发言权。

每一轮（`game.round` span）分两阶段：

1. **Bid（抢麦）阶段** — `role.bid` span，每个角色基于「当前公共对话历史 + 自己人设」产出一个**发言意愿**：
   - 输出结构：`{eagerness: 0-10, intent: "一句话想说什么"}`（用 structured output / JSON 模式，`max_tokens` 给很小，省钱）。
   - 各角色的 bid 可并行。
2. **Speak（发言）阶段** — `role.speak` span，意愿最高者真正生成完整发言：
   - 计入 `eagerness * assertiveness` 做加权，平手随机；
   - **防饿死**：连续 N 轮没发言的角色加权重，避免一个角色独占。
3. 发言写入公共历史，进入下一轮。终止条件：达到最大轮数 / 出现约定的结束标记 / 剧情目标达成。

> 成本提示：bid 阶段每轮 N 次小调用。若想省，可后续退化为「单次 director 调用选下一个发言人」，但那更接近 GM 模式，本期先按忠实的逐角色 bid 实现，开关可配。

### 3.3 入口（`main.py`）

读角色列表 → `start_trace("textgame")` → 跑 orchestrator 到结束 → 打印对话 + trace 落盘路径。无真实 key 时走 mock 也能完整跑。

---

## 4. 测试切分

- `tests/base/`：纯底座，**mock 掉网络**。覆盖 config 加载/覆盖、client 入参→ep 映射、mock 响应、trace 嵌套与 JSONL 输出。
- `tests/apps/textgame/`：人设加载、bid 解析与加权选人、防饿死、一局对话端到端（底座 mock 模式）。
- pyproject 配 marker：`pytest -m base` / `pytest -m apps` 分开跑。

---

## 5. 依赖

- `volcengine-python-sdk`（方舟 Ark）或 `openai`（指向方舟 base_url）—— 二选一，倾向用方舟官方 SDK。
- `pyyaml`（配置 + 人设）
- `pytest`（测试）
- 当前 venv 是 Python 3.9，类型标注会避开 3.10+ 语法（用 `Optional[X]` 而非 `X | None`）。

---

## 6. 待你确认 / 拍板的点

1. **底座包名** `seedcore` 是否 OK？（也可叫 `seed_sdk` / `seedkit`）
2. **方舟 SDK 选型**：用 `volcengine-python-sdk` 官方 SDK，还是 `openai` SDK 指 base_url？
3. **bid（抢麦）机制**：认同「逐角色出意愿分 + 加权选人 + 防饿死」吗？还是想要更简单的实现？
4. **人设字段**：3.1 的字段够用吗？要不要加关系/记忆/情绪等。
5. Python 3.9 保持，还是想升级到 3.11+（影响类型写法与部分库）？

确认后我再开始写代码。
