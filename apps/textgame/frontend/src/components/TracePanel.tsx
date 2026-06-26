// Trace 面板：span 树（可折叠、按耗时着色、error 标红、hover 看属性）。
// 数据来源：结束后从 /trace 拉取的真实 span 树。
import { useState } from "react";
import type { SpanNode } from "../types";

function durColor(ms: number | null): string {
  if (ms == null) return "#9ca3af";
  if (ms < 50) return "#16a34a";
  if (ms < 300) return "#d97706";
  return "#dc2626";
}

function SpanRow({ node, depth }: { node: SpanNode; depth: number }) {
  const [open, setOpen] = useState(true);
  const hasChildren = node.children.length > 0;
  const attrs = Object.entries(node.attributes).filter(([k]) => k !== "error");
  const isError = node.status === "error";

  return (
    <div>
      <div
        className="flex cursor-pointer items-center gap-1 rounded px-1 py-0.5 hover:bg-gray-100"
        style={{ paddingLeft: depth * 14 + 4 }}
        onClick={() => hasChildren && setOpen(!open)}
        title={attrs.map(([k, v]) => `${k}=${JSON.stringify(v)}`).join("  ")}
      >
        <span className="w-3 text-[10px] text-gray-400">
          {hasChildren ? (open ? "▾" : "▸") : ""}
        </span>
        <span className={`text-xs ${isError ? "text-rose-600" : "text-gray-700"}`}>{node.name}</span>
        {node.duration_ms != null && (
          <span className="text-[11px] font-mono" style={{ color: durColor(node.duration_ms) }}>
            {node.duration_ms}ms
          </span>
        )}
        {isError && <span className="text-[10px] text-rose-500">[error]</span>}
        {attrs.slice(0, 3).map(([k, v]) => (
          <span key={k} className="text-[10px] text-gray-400">
            {k}={typeof v === "string" ? v : JSON.stringify(v)}
          </span>
        ))}
      </div>
      {open && node.children.map((c) => <SpanRow key={c.span_id} node={c} depth={depth + 1} />)}
    </div>
  );
}

export function TracePanel({ tree, loading }: { tree: SpanNode[]; loading: boolean }) {
  if (loading) return <div className="p-4 text-sm text-gray-400">加载 trace 中…</div>;
  if (!tree.length)
    return <div className="p-4 text-sm text-gray-400">对话结束后这里会显示完整 span 树。</div>;
  return (
    <div className="overflow-auto p-2 font-mono">
      {tree.map((n) => (
        <SpanRow key={n.span_id} node={n} depth={0} />
      ))}
    </div>
  );
}
