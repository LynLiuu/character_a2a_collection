// 时延面板：分层时延卡片 + 条形图（每轮耗时、每角色平均、bid vs speak、LLM p50/p95/max）。
import type { Character, Latency } from "../types";

function Bar({ label, value, max, color }: { label: string; value: number | null; max: number; color: string }) {
  const pct = value != null && max > 0 ? Math.max(2, (value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-2">
      <span className="w-20 shrink-0 truncate text-[11px] text-gray-500">{label}</span>
      <div className="h-3 flex-1 rounded bg-gray-100">
        <div className="h-3 rounded" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="w-16 shrink-0 text-right text-[11px] font-mono text-gray-600">
        {value != null ? `${value}ms` : "—"}
      </span>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-2 text-center">
      <div className="text-base font-semibold text-gray-900">{value ?? "—"}</div>
      <div className="text-[11px] text-gray-400">{label}</div>
    </div>
  );
}

export function LatencyPanel({
  latency,
  characters,
  loading,
}: {
  latency: Latency | null;
  characters: Character[];
  loading: boolean;
}) {
  if (loading) return <div className="p-4 text-sm text-gray-400">加载时延中…</div>;
  if (!latency) return <div className="p-4 text-sm text-gray-400">对话结束后这里会显示分层时延统计。</div>;

  const byId = new Map(characters.map((c) => [c.id, c]));
  const roundMax = Math.max(1, ...latency.rounds.map((r) => r.duration_ms ?? 0));
  const roleEntries = Object.entries(latency.per_role);
  const roleMax = Math.max(1, ...roleEntries.map(([, v]) => v.avg_speak_ms ?? 0));
  const phaseMax = Math.max(1, latency.phases.bid_avg_ms ?? 0, latency.phases.speak_avg_ms ?? 0);

  return (
    <div className="flex flex-col gap-4 overflow-auto p-3">
      <div className="grid grid-cols-3 gap-2">
        <Stat label="总时延" value={latency.total_ms != null ? `${latency.total_ms}ms` : null} />
        <Stat label="轮数" value={latency.round_count} />
        <Stat label="平均每轮" value={latency.avg_round_ms != null ? `${latency.avg_round_ms}ms` : null} />
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold text-gray-600">每轮耗时</h3>
        <div className="flex flex-col gap-1">
          {latency.rounds.map((r, i) => (
            <Bar
              key={i}
              label={`第${r.round}轮${r.winner ? ` · ${byId.get(r.winner)?.name ?? r.winner}` : ""}`}
              value={r.duration_ms}
              max={roundMax}
              color="#58a6ff"
            />
          ))}
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold text-gray-600">每角色平均 speak 时延</h3>
        <div className="flex flex-col gap-1">
          {roleEntries.map(([rid, v]) => {
            const c = byId.get(rid);
            return (
              <Bar
                key={rid}
                label={`${c?.avatar ?? ""}${c?.name ?? rid}(×${v.speaks})`}
                value={v.avg_speak_ms}
                max={roleMax}
                color={c?.color ?? "#8b949e"}
              />
            );
          })}
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold text-gray-600">阶段分解</h3>
        <div className="flex flex-col gap-1">
          <Bar label={`bid(×${latency.phases.bid_count})`} value={latency.phases.bid_avg_ms} max={phaseMax} color="#bc8cff" />
          <Bar label={`speak(×${latency.phases.speak_count})`} value={latency.phases.speak_avg_ms} max={phaseMax} color="#39c5cf" />
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold text-gray-600">LLM 调用（共 {latency.llm.count} 次）</h3>
        <div className="grid grid-cols-3 gap-2">
          <Stat label="p50" value={latency.llm.p50_ms != null ? `${latency.llm.p50_ms}ms` : null} />
          <Stat label="p95" value={latency.llm.p95_ms != null ? `${latency.llm.p95_ms}ms` : null} />
          <Stat label="max" value={latency.llm.max_ms != null ? `${latency.llm.max_ms}ms` : null} />
        </div>
      </div>
    </div>
  );
}
