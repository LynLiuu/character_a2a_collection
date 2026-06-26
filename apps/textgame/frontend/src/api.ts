// REST 封装：人设卡 CRUD + 会话/trace/时延。
import type {
  Character,
  CharacterDraft,
  Latency,
  SessionRecord,
  SessionSummary,
  SpanNode,
} from "./types";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  health: () => fetch("/api/health").then((r) => jsonOrThrow<{ ok: boolean; mock: boolean; model: string }>(r)),

  listCharacters: () => fetch("/api/characters").then((r) => jsonOrThrow<Character[]>(r)),

  createCharacter: (c: CharacterDraft) =>
    fetch("/api/characters", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(c),
    }).then((r) => jsonOrThrow<Character>(r)),

  updateCharacter: (id: string, c: CharacterDraft) =>
    fetch(`/api/characters/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(c),
    }).then((r) => jsonOrThrow<Character>(r)),

  deleteCharacter: (id: string) =>
    fetch(`/api/characters/${id}`, { method: "DELETE" }).then((r) => jsonOrThrow<void>(r)),

  listSessions: () => fetch("/api/sessions").then((r) => jsonOrThrow<SessionSummary[]>(r)),

  getSession: (id: string) => fetch(`/api/sessions/${id}`).then((r) => jsonOrThrow<SessionRecord>(r)),

  getTrace: (id: string) =>
    fetch(`/api/sessions/${id}/trace`).then((r) => jsonOrThrow<{ trace_id: string; tree: SpanNode[] }>(r)),

  getLatency: (id: string) => fetch(`/api/sessions/${id}/latency`).then((r) => jsonOrThrow<Latency>(r)),
};
