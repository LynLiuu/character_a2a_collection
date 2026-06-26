// 主应用：三栏布局 + 人设卡编辑抽屉 + 历史会话回看。
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { CharacterEditor } from "./components/CharacterEditor";
import { ControlBar } from "./components/ControlBar";
import { ConversationStream } from "./components/ConversationStream";
import { LatencyPanel } from "./components/LatencyPanel";
import { RoleSidebar } from "./components/RoleSidebar";
import { SessionHistory } from "./components/SessionHistory";
import { TracePanel } from "./components/TracePanel";
import type { Character, ChatItem, Latency, SessionSummary, SpanNode } from "./types";
import { useSession } from "./useSession";

type RightTab = "trace" | "latency" | "history";

export default function App() {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [scene, setScene] = useState("");
  const [maxRounds, setMaxRounds] = useState("");
  const [mock, setMock] = useState<boolean | null>(null);

  const [editorOpen, setEditorOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<"create" | "edit">("create");
  const [editTarget, setEditTarget] = useState<Character | null>(null);

  const [rightTab, setRightTab] = useState<RightTab>("trace");
  const [rightOpen, setRightOpen] = useState(false); // 右侧面板默认收起
  const [sessions, setSessions] = useState<SessionSummary[]>([]);

  // 结果数据（实时会话或历史回看共用）
  const [viewItems, setViewItems] = useState<ChatItem[] | null>(null); // 非空=正在看历史
  const [viewScene, setViewScene] = useState("");
  const [trace, setTrace] = useState<SpanNode[]>([]);
  const [latency, setLatency] = useState<Latency | null>(null);
  const [resultLoading, setResultLoading] = useState(false);
  const [openHistoryId, setOpenHistoryId] = useState<string | null>(null);

  const { state, start, pause, resume, stop, forceSpeaker, inject, reset } = useSession();

  const loadCharacters = useCallback(async () => {
    const cs = await api.listCharacters();
    setCharacters(cs);
    setSelected((sel) => sel.filter((id) => cs.some((c) => c.id === id)));
  }, []);

  const loadSessions = useCallback(async () => {
    try {
      setSessions(await api.listSessions());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    loadCharacters();
    loadSessions();
    api.health().then((h) => setMock(h.mock)).catch(() => setMock(null));
  }, [loadCharacters, loadSessions]);

  // 默认选中前三个角色
  useEffect(() => {
    if (characters.length && selected.length === 0) {
      setSelected(characters.slice(0, 3).map((c) => c.id));
    }
  }, [characters]); // eslint-disable-line react-hooks/exhaustive-deps

  // 实时会话结束后，拉取该会话的 trace + 时延
  useEffect(() => {
    if (state.status === "ended" && state.sessionId) {
      const sid = state.sessionId;
      setResultLoading(true);
      Promise.all([api.getTrace(sid), api.getLatency(sid)])
        .then(([t, l]) => {
          setTrace(t.tree);
          setLatency(l);
        })
        .catch(() => {})
        .finally(() => setResultLoading(false));
      loadSessions();
    }
  }, [state.status, state.sessionId, loadSessions]);

  const toggle = (id: string) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const onStart = () => {
    setViewItems(null);
    setOpenHistoryId(null);
    setTrace([]);
    setLatency(null);
    start({
      scene: scene.trim(),
      roles: selected,
      max_rounds: maxRounds ? parseInt(maxRounds, 10) : null,
    });
  };

  const openHistory = async (id: string) => {
    setResultLoading(true);
    setOpenHistoryId(id);
    try {
      const [rec, t, l] = await Promise.all([api.getSession(id), api.getTrace(id), api.getLatency(id)]);
      setViewItems(rec.turns);
      setViewScene(rec.scene);
      setTrace(t.tree);
      setLatency(l);
      setRightOpen(true);
      if (rightTab === "history") setRightTab("trace");
    } catch {
      /* ignore */
    } finally {
      setResultLoading(false);
    }
  };

  const backToLive = () => {
    setViewItems(null);
    setOpenHistoryId(null);
    setTrace([]);
    setLatency(null);
    reset();
  };

  const isHistory = viewItems !== null;
  const streamItems = isHistory ? viewItems! : state.items;
  const streamScene = isHistory ? viewScene : scene;

  const statusLabel = useMemo(() => {
    if (isHistory) return "📜 历史回看";
    switch (state.status) {
      case "connecting": return "连接中…";
      case "running": return `▶ 进行中 · 第${state.currentRound}轮`;
      case "paused": return "⏸ 已暂停";
      case "ended": return `■ 已结束（${state.endedReason} · ${state.totalTurns}轮）`;
      case "error": return `⚠ ${state.error}`;
      default: return "就绪";
    }
  }, [isHistory, state]);

  const controlsDisabled = !(state.status === "running" || state.status === "paused");

  return (
    <div className="flex h-full flex-col bg-white text-gray-800">
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-4 py-2.5">
        <h1 className="text-sm font-semibold text-gray-900">Seed Character · 多 Agent 文游</h1>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400">{statusLabel}</span>
          <button
            onClick={() => setRightOpen((o) => !o)}
            className={`rounded-md border px-2.5 py-1 text-xs font-medium transition ${
              rightOpen
                ? "border-gray-300 bg-gray-100 text-gray-700 hover:bg-gray-200"
                : "border-gray-200 text-gray-500 hover:bg-gray-50"
            }`}
            title="展开/收起 Trace·时延·历史面板"
          >
            {rightOpen ? "收起面板 ›" : "‹ Trace·时延·历史"}
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {/* 左：角色栏 */}
        <aside className="w-64 shrink-0 border-r border-gray-200 bg-gray-50/60">
          <RoleSidebar
            characters={characters}
            selected={selected}
            onToggle={toggle}
            onEdit={(id) => {
              setEditorMode("edit");
              setEditTarget(characters.find((c) => c.id === id) ?? null);
              setEditorOpen(true);
            }}
            onNew={() => {
              setEditorMode("create");
              setEditTarget(null);
              setEditorOpen(true);
            }}
            scene={scene}
            setScene={setScene}
            maxRounds={maxRounds}
            setMaxRounds={setMaxRounds}
            status={state.status}
            onStart={onStart}
            onPause={pause}
            onResume={resume}
            onStop={stop}
            mock={mock}
          />
        </aside>

        {/* 中：对话流 + 控制条 */}
        <main className="flex min-w-0 flex-1 flex-col">
          {isHistory && (
            <div className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-1.5 text-xs text-gray-500">
              <span>正在回看历史会话</span>
              <button onClick={backToLive} className="rounded border border-gray-200 bg-white px-2 py-0.5 text-gray-600 hover:bg-gray-100">
                ← 返回实时
              </button>
            </div>
          )}
          <div className="min-h-0 flex-1">
            <ConversationStream scene={streamScene} items={streamItems} characters={characters} />
          </div>
          {!isHistory && (
            <ControlBar
              characters={characters}
              selected={selected}
              disabled={controlsDisabled}
              onForceSpeaker={forceSpeaker}
              onInject={inject}
            />
          )}
        </main>

        {/* 右：Trace / 时延 / 历史（默认收起） */}
        {rightOpen && (
          <aside className="flex w-96 shrink-0 flex-col border-l border-gray-200 bg-white">
            <div className="flex border-b border-gray-200">
              {(["trace", "latency", "history"] as RightTab[]).map((t) => (
                <button
                  key={t}
                  onClick={() => setRightTab(t)}
                  className={`flex-1 py-2 text-xs font-medium transition ${
                    rightTab === t
                      ? "border-b-2 border-indigo-500 text-gray-900"
                      : "text-gray-400 hover:text-gray-600"
                  }`}
                >
                  {t === "trace" ? "Trace" : t === "latency" ? "时延" : "历史"}
                </button>
              ))}
            </div>
            <div className="min-h-0 flex-1 overflow-hidden">
              {rightTab === "trace" && <TracePanel tree={trace} loading={resultLoading} />}
              {rightTab === "latency" && (
                <LatencyPanel latency={latency} characters={characters} loading={resultLoading} />
              )}
              {rightTab === "history" && (
                <SessionHistory
                  sessions={sessions}
                  activeId={openHistoryId}
                  onOpen={openHistory}
                  onRefresh={loadSessions}
                />
              )}
            </div>
          </aside>
        )}
      </div>

      <CharacterEditor
        open={editorOpen}
        mode={editorMode}
        initial={editTarget}
        onClose={() => setEditorOpen(false)}
        onSaved={loadCharacters}
      />
    </div>
  );
}
