// 历史会话列表：回看过去对话 + trace + 时延。
import type { SessionSummary } from "../types";

interface Props {
  sessions: SessionSummary[];
  activeId: string | null;
  onOpen: (id: string) => void;
  onRefresh: () => void;
}

function fmtTime(ts: number): string {
  const d = new Date(ts * 1000);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(
    d.getMinutes()
  ).padStart(2, "0")}`;
}

export function SessionHistory({ sessions, activeId, onOpen, onRefresh }: Props) {
  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between p-2">
        <span className="text-xs text-gray-400">{sessions.length} 条历史</span>
        <button onClick={onRefresh} className="rounded px-2 py-0.5 text-xs text-gray-500 hover:bg-gray-100" title="刷新">
          ↻
        </button>
      </div>
      <div className="flex-1 overflow-auto px-2 pb-2">
        {sessions.length === 0 && <div className="p-2 text-xs text-gray-400">还没有历史会话。</div>}
        {sessions.map((s) => (
          <button
            key={s.id}
            onClick={() => onOpen(s.id)}
            className={`mb-1 w-full rounded-lg border p-2 text-left transition ${
              activeId === s.id ? "border-indigo-300 bg-indigo-50" : "border-gray-200 bg-white hover:bg-gray-50"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-700">{fmtTime(s.created)}</span>
              <span className="text-[10px] text-gray-400">
                {s.total_turns}轮 · {s.reason}
              </span>
            </div>
            <div className="mt-0.5 truncate text-xs text-gray-500">{s.scene || "（无场景）"}</div>
            <div className="mt-0.5 text-[11px] text-gray-400">{s.roles.join(" · ")}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
