// 对话流：场景 + 气泡逐条渲染，自动滚到底。
import { useEffect, useRef } from "react";
import type { Character, ChatItem } from "../types";

interface Props {
  scene: string;
  items: ChatItem[];
  characters: Character[];
}

export function ConversationStream({ scene, items, characters }: Props) {
  const endRef = useRef<HTMLDivElement | null>(null);
  const byId = new Map(characters.map((c) => [c.id, c]));

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [items.length]);

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto bg-white p-4">
      {scene && (
        <div className="mx-auto max-w-2xl rounded-lg border border-gray-200 bg-gray-50 px-4 py-2 text-center text-sm text-gray-500">
          【场景】{scene}
        </div>
      )}

      {items.length === 0 && !scene && (
        <div className="flex h-full items-center justify-center text-sm text-gray-400">
          选择角色、设定场景，点「开始」让他们对话起来
        </div>
      )}

      {items.map((it, i) => {
        if (it.kind === "narration") {
          return (
            <div key={i} className="mx-auto max-w-2xl text-center text-sm italic text-amber-600">
              — {it.text} —
            </div>
          );
        }
        const c = it.role ? byId.get(it.role) : undefined;
        const color = c?.color ?? "#6b7280";
        return (
          <div key={i} className="flex gap-3">
            <span
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-lg"
              style={{ background: color + "22" }}
              title={it.name}
            >
              {c?.avatar ?? "🎭"}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-medium" style={{ color }}>
                  {it.name}
                </span>
                <span className="text-[11px] text-gray-400">
                  第{it.round}轮{it.latency_ms != null ? ` · ${it.latency_ms}ms` : ""}
                </span>
              </div>
              <div
                className="mt-1 inline-block rounded-2xl rounded-tl-sm border px-3 py-2 text-sm leading-relaxed text-gray-800"
                style={{ background: color + "12", borderColor: color + "30" }}
              >
                {it.text}
              </div>
            </div>
          </div>
        );
      })}
      <div ref={endRef} />
    </div>
  );
}
