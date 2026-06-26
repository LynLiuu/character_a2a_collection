// 与后端契约对应的类型定义。

export interface Character {
  id: string;
  name: string;
  avatar: string;
  color: string;
  goals: string[];
  speaking_style: string;
  assertiveness: number;
  persona: string;
}

export type CharacterDraft = Omit<Character, "avatar" | "color"> & {
  avatar?: string;
  color?: string;
};

// --- WebSocket 事件（服务端 → 客户端） ---
export interface EvSession { type: "session"; id: string; }
export interface EvRoundStart { type: "round_start"; round: number; }
export interface EvBid {
  type: "bid"; round: number; role: string;
  eagerness: number; intent: string; weight: number;
}
export interface EvPick { type: "pick"; round: number; winner: string; forced: boolean; }
export interface EvTurn {
  type: "turn"; round: number; role: string; name: string;
  text: string; latency_ms: number;
}
export interface EvNarration { type: "narration"; round: number; text: string; }
export interface EvRoundEnd { type: "round_end"; round: number; duration_ms: number; }
export interface EvEnded { type: "ended"; reason: string; total_turns: number; trace_path: string | null; }
export interface EvError { type: "error"; msg: string; }
export interface EvState { type: "state"; paused: boolean; }

export type ServerEvent =
  | EvSession | EvRoundStart | EvBid | EvPick | EvTurn
  | EvNarration | EvRoundEnd | EvEnded | EvError | EvState;

// 对话流里的一条消息（发言或旁白）
export interface ChatItem {
  kind: "turn" | "narration";
  round: number;
  role?: string;
  name?: string;
  text: string;
  latency_ms?: number;
}

// --- Trace ---
export interface SpanNode {
  span_id: string;
  name: string;
  duration_ms: number | null;
  status: string;
  depth: number;
  attributes: Record<string, unknown>;
  children: SpanNode[];
}

// --- Latency 聚合 ---
export interface RoundLatency { round: number | null; duration_ms: number | null; winner: string | null; }
export interface PerRole { speaks: number; total_ms: number; avg_speak_ms: number | null; }
export interface Latency {
  total_ms: number | null;
  rounds: RoundLatency[];
  round_count: number;
  avg_round_ms: number | null;
  per_role: Record<string, PerRole>;
  phases: {
    bid_avg_ms: number | null; bid_count: number;
    speak_avg_ms: number | null; speak_count: number;
  };
  llm: { count: number; p50_ms: number | null; p95_ms: number | null; max_ms: number | null; };
}

// --- 会话列表/记录 ---
export interface SessionSummary {
  id: string;
  created: number;
  scene: string;
  roles: string[];
  total_turns: number;
  reason: string;
  trace_id: string | null;
}
export interface SessionRecord extends SessionSummary {
  max_rounds: number | null;
  trace_path: string | null;
  turns: ChatItem[];
}
