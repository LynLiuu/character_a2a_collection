// 人设卡编辑抽屉：左字段表单 + 右 Markdown 编辑器(带实时预览)。保存写回磁盘。
import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import { api } from "../api";
import type { Character, CharacterDraft } from "../types";

interface Props {
  // null = 关闭；{} 形态由 mode 区分
  open: boolean;
  mode: "create" | "edit";
  initial: Character | null;
  onClose: () => void;
  onSaved: () => void;
}

const BLANK: CharacterDraft = {
  id: "",
  name: "",
  persona: "",
  goals: [],
  speaking_style: "",
  assertiveness: 0.5,
  avatar: "🎭",
  color: "#8b8b8b",
};

export function CharacterEditor({ open, mode, initial, onClose, onSaved }: Props) {
  const [form, setForm] = useState<CharacterDraft>(BLANK);
  const [goalsText, setGoalsText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (mode === "edit" && initial) {
      setForm({ ...initial });
      setGoalsText(initial.goals.join("\n"));
    } else {
      setForm(BLANK);
      setGoalsText("");
    }
    setError(null);
  }, [open, mode, initial]);

  if (!open) return null;

  const set = <K extends keyof CharacterDraft>(k: K, v: CharacterDraft[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    setSaving(true);
    setError(null);
    const payload: CharacterDraft = {
      ...form,
      goals: goalsText.split("\n").map((g) => g.trim()).filter(Boolean),
    };
    try {
      if (mode === "create") await api.createCharacter(payload);
      else await api.updateCharacter(form.id, payload);
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const del = async () => {
    if (mode !== "edit") return;
    if (!confirm(`确定删除角色「${form.name}」？`)) return;
    setSaving(true);
    try {
      await api.deleteCharacter(form.id);
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-gray-900/30" onClick={onClose}>
      <div
        className="flex h-full w-full max-w-3xl flex-col bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-gray-200 p-3">
          <h2 className="text-sm font-semibold text-gray-900">
            {mode === "create" ? "新建角色" : `编辑：${form.name}`}
          </h2>
          <button onClick={onClose} className="rounded px-2 text-gray-400 hover:text-gray-700">
            ✕
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* 字段表单 */}
          <div className="w-72 shrink-0 space-y-3 overflow-y-auto border-r border-gray-200 bg-gray-50/60 p-3">
            <Field label="ID（小写字母开头）">
              <input
                value={form.id}
                onChange={(e) => set("id", e.target.value)}
                disabled={mode === "edit"}
                placeholder="alice"
                className="w-full rounded-md border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-800 outline-none focus:border-indigo-400 disabled:opacity-50"
              />
            </Field>
            <Field label="名字">
              <input
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
                placeholder="爱丽丝"
                className="w-full rounded-md border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-800 outline-none focus:border-indigo-400"
              />
            </Field>
            <div className="flex gap-2">
              <Field label="头像 emoji">
                <input
                  value={form.avatar ?? ""}
                  onChange={(e) => set("avatar", e.target.value)}
                  placeholder="🗺️"
                  className="w-full rounded-md border border-gray-200 bg-white px-2 py-1.5 text-center text-lg outline-none focus:border-indigo-400"
                />
              </Field>
              <Field label="主题色">
                <input
                  type="color"
                  value={form.color ?? "#8b8b8b"}
                  onChange={(e) => set("color", e.target.value)}
                  className="h-9 w-full rounded-md border border-gray-200 bg-white"
                />
              </Field>
            </div>
            <Field label="目标（每行一个）">
              <textarea
                value={goalsText}
                onChange={(e) => setGoalsText(e.target.value)}
                rows={3}
                placeholder="找到古井&#10;弄清被困原因"
                className="w-full resize-none rounded-md border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-800 outline-none focus:border-indigo-400"
              />
            </Field>
            <Field label="说话风格">
              <input
                value={form.speaking_style}
                onChange={(e) => set("speaking_style", e.target.value)}
                placeholder="短句，爱用反问"
                className="w-full rounded-md border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-800 outline-none focus:border-indigo-400"
              />
            </Field>
            <Field label={`果断度 ${form.assertiveness.toFixed(2)}`}>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={form.assertiveness}
                onChange={(e) => set("assertiveness", parseFloat(e.target.value))}
                className="w-full accent-indigo-600"
              />
            </Field>
          </div>

          {/* Markdown 人设正文 */}
          <div className="flex flex-1 flex-col p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-semibold text-gray-600">人设正文（Markdown）</span>
              <button
                onClick={() => setShowPreview((p) => !p)}
                className="rounded-md border border-gray-200 bg-white px-2 py-0.5 text-xs text-gray-600 hover:bg-gray-100"
              >
                {showPreview ? "编辑" : "预览"}
              </button>
            </div>
            {showPreview ? (
              <div className="md-preview flex-1 overflow-auto rounded-md border border-gray-200 bg-gray-50 p-3 text-sm text-gray-800">
                <Markdown>{form.persona || "*（空）*"}</Markdown>
              </div>
            ) : (
              <textarea
                value={form.persona}
                onChange={(e) => set("persona", e.target.value)}
                placeholder="你是爱丽丝，一个好奇心旺盛、说话直接的少女探险家……"
                className="flex-1 resize-none rounded-md border border-gray-200 bg-white p-3 font-mono text-sm text-gray-800 outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200"
              />
            )}
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-gray-200 p-3">
          <div className="text-xs text-rose-500">{error}</div>
          <div className="flex gap-2">
            {mode === "edit" && (
              <button
                onClick={del}
                disabled={saving}
                className="rounded-md bg-rose-500 px-3 py-1.5 text-sm text-white hover:bg-rose-400 disabled:opacity-50"
              >
                删除
              </button>
            )}
            <button onClick={onClose} className="rounded-md border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100">
              取消
            </button>
            <button
              onClick={save}
              disabled={saving || !form.id || !form.name}
              className="rounded-md bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
            >
              {saving ? "保存中…" : "保存"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-gray-500">{label}</span>
      {children}
    </label>
  );
}
