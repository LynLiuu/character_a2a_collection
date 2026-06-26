// 控制条：指定下一发言者 + 插入旁白。仅在对话进行中可用。
import { useState } from "react";
import type { Character } from "../types";

interface Props {
  characters: Character[];
  selected: string[];
  disabled: boolean;
  onForceSpeaker: (role: string) => void;
  onInject: (text: string) => void;
}

export function ControlBar({ characters, selected, disabled, onForceSpeaker, onInject }: Props) {
  const [narration, setNarration] = useState("");
  const picks = characters.filter((c) => selected.includes(c.id));

  const submitNarration = () => {
    const t = narration.trim();
    if (!t) return;
    onInject(t);
    setNarration("");
  };

  return (
    <div className="flex items-center gap-3 border-t border-gray-200 bg-gray-50/60 p-3">
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">下一个</span>
        <select
          disabled={disabled}
          defaultValue=""
          onChange={(e) => {
            if (e.target.value) {
              onForceSpeaker(e.target.value);
              e.target.value = "";
            }
          }}
          className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-700 outline-none focus:border-indigo-400 disabled:opacity-50"
        >
          <option value="">自动</option>
          {picks.map((c) => (
            <option key={c.id} value={c.id}>
              {c.avatar} {c.name}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-1 items-center gap-2">
        <input
          value={narration}
          onChange={(e) => setNarration(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submitNarration()}
          disabled={disabled}
          placeholder="插入旁白，如「远处传来狼嚎」回车发送"
          className="flex-1 rounded-md border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200 disabled:opacity-50"
        />
        <button
          onClick={submitNarration}
          disabled={disabled}
          className="rounded-md border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-50"
        >
          旁白
        </button>
      </div>
    </div>
  );
}
