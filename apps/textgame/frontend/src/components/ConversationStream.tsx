// 对话流：场景 + 气泡逐条渲染，自动滚到底。
import { useEffect, useRef } from "react";
import type { Character, ChatItem } from "../types";

interface Props {
  scene: string;
  items: ChatItem[];
  characters: Character[];
  backgroundUrl?: string | null;
}

export function ConversationStream({ scene, items, characters, backgroundUrl }: Props) {
  const endRef = useRef<HTMLDivElement | null>(null);
  const byId = new Map(characters.map((c) => [c.id, c]));

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [items.length]);

  return (
    <div className="relative h-full overflow-hidden">
      {/* 动态背景：仅略带透明、平滑淡入，置于对话流下层，不拦截滚动/点击 */}
      <div
        key={backgroundUrl ?? "none"}
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-cover bg-center transition-opacity duration-1000 ease-out"
        style={{
          backgroundImage: backgroundUrl ? `url("${backgroundUrl}")` : undefined,
          opacity: backgroundUrl ? 0.85 : 0,
        }}
      />
      {/* 极轻的白色蒙版，仅为保证气泡文字可读，不明显压暗背景 */}
      <div className="pointer-events-none absolute inset-0 bg-white/15" />

      <div className="relative flex h-full flex-col gap-3 overflow-y-auto p-4">
        {scene && (
          <div className="mx-auto max-w-2xl rounded-lg border border-gray-200 bg-gray-50/80 px-4 py-2 text-center text-sm text-gray-500 backdrop-blur-sm">
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
            if (it.source === "gm") {
              return (
                <div key={i} className="mx-auto max-w-2xl">
                  <div className="rounded-lg border border-amber-200 bg-amber-50/85 px-4 py-2.5 text-center text-sm leading-relaxed text-amber-800 shadow-sm backdrop-blur-md">
                    <span className="mr-1.5 align-middle text-[11px] font-medium uppercase tracking-wide text-amber-500">
                      旁白
                    </span>
                    {it.text}
                  </div>
                </div>
              );
            }
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
                  className="mt-1 inline-block rounded-2xl rounded-tl-sm border px-3 py-2 text-sm leading-relaxed text-gray-800 shadow-sm backdrop-blur-md"
                  style={{ background: `color-mix(in srgb, ${color} 14%, rgba(255,255,255,0.92))`, borderColor: color + "44" }}
                >
                  {it.text}
                </div>
              </div>
            </div>
          );
        })}
        <div ref={endRef} />
      </div>
    </div>
  );
}
