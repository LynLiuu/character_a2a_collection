// 角色栏：角色卡列表 + 场景/轮数 + 开始/暂停/继续/停止控制。
import type { Character } from "../types";
import type { RunStatus } from "../useSession";

interface Props {
  characters: Character[];
  selected: string[];
  onToggle: (id: string) => void;
  onEdit: (id: string) => void;
  onNew: () => void;
  scene: string;
  setScene: (s: string) => void;
  maxRounds: string;
  setMaxRounds: (s: string) => void;
  status: RunStatus;
  onStart: () => void;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
  mock: boolean | null;
}

export function RoleSidebar(props: Props) {
  const {
    characters, selected, onToggle, onEdit, onNew,
    scene, setScene, maxRounds, setMaxRounds,
    status, onStart, onPause, onResume, onStop, mock,
  } = props;

  const running = status === "running";
  const paused = status === "paused";
  const active = running || paused;

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700">角色</h2>
        <button
          onClick={onNew}
          className="rounded-md border border-gray-200 bg-white px-2 py-1 text-xs text-gray-600 hover:bg-gray-100"
        >
          + 新建
        </button>
      </div>

      <div className="flex flex-col gap-2">
        {characters.map((c) => {
          const isSel = selected.includes(c.id);
          return (
            <div
              key={c.id}
              className={`group flex items-center gap-2 rounded-lg border p-2 transition ${
                isSel ? "border-transparent shadow-sm" : "border-gray-200 bg-white"
              }`}
              style={isSel ? { background: c.color + "14", borderColor: c.color } : undefined}
            >
              <button
                onClick={() => !active && onToggle(c.id)}
                disabled={active}
                className="flex flex-1 items-center gap-2 text-left disabled:cursor-not-allowed"
                title={active ? "对话进行中不可改选角色" : "点击选择/取消"}
              >
                <span
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-lg"
                  style={{ background: c.color + "22" }}
                >
                  {c.avatar}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm text-gray-800">{c.name}</div>
                  <div className="mt-0.5 h-1 w-full rounded bg-gray-200">
                    <div
                      className="h-1 rounded"
                      style={{ width: `${c.assertiveness * 100}%`, background: c.color }}
                    />
                  </div>
                </div>
              </button>
              <button
                onClick={() => onEdit(c.id)}
                className="rounded px-1 text-xs text-gray-400 opacity-0 group-hover:opacity-100 hover:text-gray-700"
                title="编辑人设卡"
              >
                ✎
              </button>
            </div>
          );
        })}
      </div>

      <div className="mt-auto flex flex-col gap-2 border-t border-gray-200 pt-3">
        <label className="text-xs text-gray-500">场景设定</label>
        <textarea
          value={scene}
          onChange={(e) => setScene(e.target.value)}
          disabled={active}
          rows={3}
          placeholder="暮色森林深处，一口被藤蔓缠绕的古井……"
          className="resize-none rounded-md border border-gray-200 bg-white p-2 text-sm text-gray-800 outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200 disabled:opacity-60"
        />
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500">轮数</label>
          <input
            value={maxRounds}
            onChange={(e) => setMaxRounds(e.target.value.replace(/[^0-9]/g, ""))}
            disabled={active}
            placeholder="∞"
            className="w-16 rounded-md border border-gray-200 bg-white px-2 py-1 text-sm text-gray-800 outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200 disabled:opacity-60"
          />
          <span className="text-xs text-gray-400">留空 = 无限</span>
        </div>

        <div className="flex gap-2">
          {!active ? (
            <button
              onClick={onStart}
              disabled={selected.length === 0 || status === "connecting"}
              className="flex-1 rounded-md bg-indigo-600 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-40"
            >
              ▶ 开始
            </button>
          ) : (
            <>
              {running ? (
                <button onClick={onPause} className="flex-1 rounded-md bg-amber-500 py-2 text-sm font-medium text-white hover:bg-amber-400">
                  ⏸ 暂停
                </button>
              ) : (
                <button onClick={onResume} className="flex-1 rounded-md bg-indigo-600 py-2 text-sm font-medium text-white hover:bg-indigo-500">
                  ▶ 继续
                </button>
              )}
              <button onClick={onStop} className="flex-1 rounded-md bg-rose-500 py-2 text-sm font-medium text-white hover:bg-rose-400">
                ⏹ 停止
              </button>
            </>
          )}
        </div>
        {mock !== null && (
          <div className="text-center text-[11px] text-gray-400">
            {mock ? "🧪 Mock 模式（未配置真实 key/ep）" : "powered by seed character"}
          </div>
        )}
      </div>
    </div>
  );
}
