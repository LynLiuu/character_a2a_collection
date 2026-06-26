# 前端化改造计划 — 多 agent 文游 Web 应用

> 状态：**待确认**（确认后再开发）
> 日期：2026-06-26
> 基于已确认决策：React+Vite+Tailwind / WebSocket 双向 / 人设卡=字段+独立 .md / 写回磁盘 + 分层时延

## 0. 目标

把现有 `seedcore`(底座) + `apps/textgame`(引擎) 包装成一个 Web 应用：

1. **主交互界面**：选角色 → 设场景 → 开始，对话实时逐轮长出来；可暂停/继续/停止、**指定下一个发言者**、**插入旁白**。
2. **人设卡**：可视化卡片，可新建/编辑/删除；每张卡 = 结构化字段 + 一段 **Markdown 人设正文**；编辑**写回磁盘**。
3. **结果可见**：前端能看到 ① **对话记录** ② **trace**（span 树）③ **分层时延统计**。
4. 底座保持不动当 SDK 用；引擎做最小必要改造以支持「可控运行」。

---

## 1. 总体架构

```
┌─────────────── Frontend (React+Vite+Tailwind, :5173 dev) ───────────────┐
│  主交互页：角色栏 | 对话流 | 右侧(Trace / 时延 两个 tab)                  │
│  人设卡编辑抽屉： 字段表单 + Markdown 编辑器(带预览)                       │
│        │  WebSocket(实时对话/控制)        │ REST(人设CRUD/历史/时延)        │
└────────┼───────────────────────────────────┼──────────────────────────────┘
         ▼                                   ▼
┌─────────────── Backend (FastAPI + uvicorn, :8000) ──────────────────────┐
│  /ws/session            WebSocket：双向，跑一局可控对话                    │
│  /api/characters        人设卡 CRUD（读写 characters/ 目录）              │
│  /api/sessions          历史会话列表 / 对话记录 / trace / 时延聚合         │
│  静态托管 apps/textgame/frontend/dist （生产模式）                        │
└──────────┬───────────────────────────────────────────────────────────────┘
           ▼
   apps/textgame (引擎) ──► seedcore (底座：Client/Config/Trace)
```

- 后端代码放 `apps/textgame/server/`（与引擎同源），前端 `apps/textgame/frontend/`，整个 app 自包含。
- 引擎/底座是同步阻塞（`urllib` 调方舟）。对话循环跑在**后台线程**里，通过线程安全队列把事件桥接给 WS 协程；WS 收到的控制指令进另一条命令队列。这样不改造底座的同步模型。

---

## 2. 引擎改造：可控、可观察的运行

现状 `Orchestrator.run(on_turn=...)` 是一次性同步循环。为支持 WebSocket 的暂停/插话/指定发言，做**加法式**改造（保持旧用法与测试不变）：

`run(emit=None, controller=None)`：
- **`emit(event: dict)`**：把过程拆成结构化事件流，替代单一 `on_turn`（仍保留 `on_turn` 兼容）。事件类型：
  - `round_start {round}`
  - `bid {round, role, eagerness, intent, weight}`（每个角色一条）
  - `pick {round, winner}`
  - `turn {round, role, name, text, latency_ms}`
  - `narration {round, text}`（旁白插入）
  - `round_end {round, duration_ms}`
  - `ended {reason, total_turns, trace_path}` / `error {msg}`
- **`controller`**（可选，默认空=老行为）：每轮循环检查
  - `wait_if_paused()` — 暂停时阻塞，直到继续
  - `should_stop()` — 停止则收尾退出
  - `next_speaker_override()` — 指定发言者则跳过加权直接选他
  - `drain_injections()` — 取出待插入的旁白，作为 `narration` 写进公共历史（不占发言轮）

引擎仍可 headless 用：`Orchestrator(roles).run()` 不传 `emit/controller` 行为完全同现在。

新增 `apps/textgame/session.py`：
- `WsController`：用 `threading.Event`(暂停) + `queue.Queue`(命令) 实现上面的 controller 接口。
- `run_session_in_thread(config, out_queue, controller)`：在线程里跑 `Orchestrator.run`，`emit` 把事件塞进 `out_queue`。

---

## 3. 人设卡数据模型（字段 + 独立 .md）

每张卡两个文件，放在 `apps/textgame/characters/`：

```
characters/
  alice.yaml      # 元信息
  alice.md        # 人设正文（Markdown）
```

`alice.yaml`：
```yaml
id: alice
name: "爱丽丝"
avatar: "🗺️"            # emoji 头像（前端展示）
color: "#e25555"         # 气泡/卡片主题色
goals: ["找到古井", "弄清被困原因"]
speaking_style: "短句，爱用反问"
assertiveness: 0.8
```

`alice.md`（人设正文，原来内联在 yaml 的 persona 移到这里）：
```markdown
你是爱丽丝，一个好奇心旺盛、说话直接的少女探险家……
```

改造点：
- `Persona.load()`：读 `{id}.yaml` 元信息 + 同名 `{id}.md` 作为 `persona`；`.md` 不存在时回退 yaml 里的 `persona` 字段（向后兼容）。
- 迁移现有 alice/bob/cara：把它们 yaml 里的 `persona` 抽到对应 `.md`，新增 `avatar`/`color`。
- 新增 `avatar`/`color` 为可选字段，缺省给默认值。

---

## 4. 后端 API

### 4.1 WebSocket `/ws/session`
一条连接 = 一局对话。

客户端→服务端：
```jsonc
{"type":"start","scene":"...","roles":["alice","bob","cara"],"max_rounds":null}
{"type":"pause"} {"type":"resume"} {"type":"stop"}
{"type":"force_speaker","role":"bob"}     // 指定下一轮发言者
{"type":"inject","text":"远处传来狼嚎。"}   // 插入旁白
```
服务端→客户端：第 2 节列出的所有事件（逐条 JSON）。另有 `{"type":"state","paused":bool}` 回执。

### 4.2 REST 人设卡 `/api/characters`
- `GET /api/characters` → 列出所有卡（元信息 + persona 正文）
- `GET /api/characters/{id}`
- `POST /api/characters` → 新建（写 yaml+md）
- `PUT /api/characters/{id}` → 更新（写回磁盘）
- `DELETE /api/characters/{id}`
- 写入有基本校验（id 合法、必填字段、避免越权路径）。

### 4.3 REST 会话/记录 `/api/sessions`
每局结束把**对话记录**落盘 `apps/textgame/sessions/{session_id}.json`（含 turns + 元信息 + trace_id）。
- `GET /api/sessions` → 历史列表
- `GET /api/sessions/{id}` → 对话记录
- `GET /api/sessions/{id}/trace` → 解析该 trace 的 JSONL，返回 **span 树**（嵌套结构，含 duration/status/attributes）
- `GET /api/sessions/{id}/latency` → **分层时延聚合**（见 §6）

---

## 5. 前端界面设计

单页应用，主交互页三栏 + 一个可呼出的人设卡编辑抽屉。

```
┌──────────────┬────────────────────────────┬─────────────────────────┐
│ 角色栏        │        对话流(中央)         │  右侧面板 (Tab)          │
│ [🗺️ 爱丽丝]  │  【场景】暮色森林古井...     │ ┌ Trace ┬ 时延 ┐         │
│ [📜 鲍勃]    │  🗺️ 爱丽丝：这口井…          │ │ textgame 553ms        │
│ [🗡️ 卡拉]    │  📜 鲍勃：慢着…              │ │  └round1 …            │
│ + 新建角色    │  …(实时逐条长出)            │ │    ├bid alice 0.6ms   │
│ ──────────   │                            │ │    └speak …           │
│ 场景输入框    │                            │ └ (可折叠 span 树)       │
│ 轮数:[∞]      │  ┌── 控制条 ───────────┐    │  时延 tab:              │
│ ▶开始 ⏸暂停  │  │下一个:[自动▾] 旁白:[__]│   │  总/每轮/每角色/        │
│ ⏹停止        │  └──────────────────────┘   │  bid·speak / p50·p95    │
└──────────────┴────────────────────────────┴─────────────────────────┘
```

组件：
- **RoleSidebar**：角色卡列表（头像+名+assertiveness 条），点开 → **CharacterEditor 抽屉**；含「新建角色」。场景输入、轮数(∞/数字)、开始/暂停/继续/停止按钮。
- **ConversationStream**：按角色气泡渲染（头像、主题色），WS `turn`/`narration` 事件实时追加，自动滚到底。
- **ControlBar**：`下一个发言者` 下拉（自动/指定某角色 → 发 `force_speaker`）、旁白输入框（发 `inject`）。
- **CharacterEditor**（抽屉/弹窗）：左字段表单（name/avatar/color/goals/style/assertiveness），右 **Markdown 编辑器 + 实时预览**（编辑 persona 正文）；保存 → `PUT/POST`，写回磁盘。
- **TracePanel**：可折叠 span 树，按 duration 着色，error 标红，hover 看 attributes。数据来自 WS 实时累积 + 结束后 `/trace` 校正。
- **LatencyPanel**：分层时延卡片 + 简单条形图（每轮耗时、每角色平均、bid vs speak）。

样式：Tailwind，深色主题，紧凑信息密度。

---

## 6. 三类结果如何呈现

1. **对话记录**：中央对话流实时显示；落盘 `apps/textgame/sessions/{id}.json`；历史可在「会话列表」回看。
2. **Trace**：右侧 Trace tab 的 span 树（`textgame→round→bid/speak→llm.call`），实时增量 + 结束后从 JSONL 校正；保留底座已埋的全部属性（model/ep/token/latency/mock…）。
3. **分层时延**（来自 trace 的 `latency_ms`/span duration）：
   - 总时延、轮数、平均每轮
   - 每角色：发言次数、平均 speak 时延
   - 阶段分解：bid 平均 vs speak 平均
   - LLM 调用 **p50 / p95 / max**
   - 每轮耗时条形图

---

## 7. 文件结构（新增）

```
apps/textgame/
  server/
    __init__.py
    app.py              # FastAPI 实例 + 路由挂载 + 静态托管
    ws.py               # /ws/session 处理 + 事件桥接
    characters_api.py   # 人设卡 CRUD
    sessions_api.py     # 历史/trace 树/时延聚合
    latency.py          # 从 trace JSONL 算分层时延
  session.py            # WsController + run_session_in_thread
  characters/
    *.yaml + *.md       # 迁移后的人设卡
  sessions/             # 对话记录落盘 (gitignore)
  traces/               # trace JSONL 落盘 (gitignore)
  frontend/             # React+Vite+Tailwind
    src/ ... (组件如上)
    vite.config.ts      # dev proxy 到 :8000
tests/apps/textgame/
  test_characters_api.py
  test_session_control.py   # 暂停/停止/指定发言/插旁白
  test_latency.py
```

新增依赖：后端 `fastapi`、`uvicorn[standard]`（含 websockets）；前端 Node + `react`/`vite`/`tailwindcss`/`react-markdown`。

---

## 8. 运行方式

开发：
```
uvicorn apps.textgame.server.app:app --reload   # 后端 :8000
cd apps/textgame/frontend && npm install && npm run dev   # 前端 :5173（代理到 8000）
```
一体化（构建后单端口）：
```
cd apps/textgame/frontend && npm run build   # 产出 apps/textgame/frontend/dist/
uvicorn apps.textgame.server.app:app   # 后端直接托管前端 :8000
```
无真实 key/ep 时仍自动 mock，前端可完整体验。

---

## 9. 分阶段实施

- **P1 人设卡重构**：yaml+md 模型、`Persona.load` 改造、迁移 3 张卡、CRUD API + 测试。
- **P2 可控引擎**：`Orchestrator.run(emit, controller)` 加法改造、`session.py`、headless 控制测试。
- **P3 WebSocket**：`/ws/session` 协议、线程↔协程桥接、start/pause/resume/stop/force/inject。
- **P4 记录与时延**：对话落盘、`/sessions` 系列、trace 树、`latency.py` 聚合 + 测试。
- **P5 前端**：脚手架(Vite+Tailwind)→ 主交互三栏 → 人设卡编辑器 → Trace 面板 → 时延面板。
- **P6 收尾**：构建托管、README、CI 跑后端测试（前端 lint 可选）。

---

## 10. 待你拍板的点

1. 文件结构：后端放 `apps/textgame/server/` + 前端 `apps/textgame/frontend/`，OK 吗？
2. 控制能力先做哪些？建议首版：暂停/继续/停止/**指定下一发言者**/**插入旁白**。够吗？
3. 历史会话列表（回看过去对话/trace）要不要进首版？（建议要，落盘很轻）
4. 头像用 emoji + 主题色够吗？还是要上传图片？
5. 端口 8000/5173 可以吗？

确认后我按 P1→P6 开干。
