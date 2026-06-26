// useSession：管理一条 WebSocket 连接的生命周期与状态累积。
// 暴露 start/pause/resume/stop/forceSpeaker/inject 控制函数，
// 以及对话流(items)、实时 trace、时延、bid、连接/运行状态。
import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatItem, EvBid, ServerEvent } from "./types";

export type RunStatus = "idle" | "connecting" | "running" | "paused" | "ended" | "error";

interface StartConfig {
  scene: string;
  roles: string[];
  max_rounds: number | null;
}

// 实时把 turn/round span 累积成一棵简化 trace 树供 TracePanel 展示
interface LiveRound {
  round: number;
  duration_ms?: number;
  winner?: string;
  forced?: boolean;
  bids: EvBid[];
}

export interface SessionState {
  status: RunStatus;
  sessionId: string | null;
  items: ChatItem[];
  rounds: LiveRound[];
  currentRound: number;
  error: string | null;
  endedReason: string | null;
  totalTurns: number;
}

const EMPTY: SessionState = {
  status: "idle",
  sessionId: null,
  items: [],
  rounds: [],
  currentRound: 0,
  error: null,
  endedReason: null,
  totalTurns: 0,
};

export function useSession() {
  const wsRef = useRef<WebSocket | null>(null);
  const [state, setState] = useState<SessionState>(EMPTY);

  const send = useCallback((msg: Record<string, unknown>) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
  }, []);

  const handleEvent = useCallback((ev: ServerEvent) => {
    setState((s) => {
      switch (ev.type) {
        case "session":
          return { ...s, sessionId: ev.id, status: "running" };
        case "round_start":
          return {
            ...s,
            currentRound: ev.round,
            rounds: [...s.rounds, { round: ev.round, bids: [] }],
          };
        case "bid": {
          const rounds = s.rounds.map((r) =>
            r.round === ev.round ? { ...r, bids: [...r.bids, ev] } : r
          );
          return { ...s, rounds };
        }
        case "pick": {
          const rounds = s.rounds.map((r) =>
            r.round === ev.round ? { ...r, winner: ev.winner, forced: ev.forced } : r
          );
          return { ...s, rounds };
        }
        case "turn":
          return {
            ...s,
            items: [
              ...s.items,
              {
                kind: "turn",
                round: ev.round,
                role: ev.role,
                name: ev.name,
                text: ev.text,
                latency_ms: ev.latency_ms,
              },
            ],
          };
        case "narration":
          return {
            ...s,
            items: [...s.items, { kind: "narration", round: ev.round, text: ev.text }],
          };
        case "round_end": {
          const rounds = s.rounds.map((r) =>
            r.round === ev.round ? { ...r, duration_ms: ev.duration_ms } : r
          );
          return { ...s, rounds };
        }
        case "ended":
          return { ...s, status: "ended", endedReason: ev.reason, totalTurns: ev.total_turns };
        case "error":
          return { ...s, status: "error", error: ev.msg };
        case "state":
          return { ...s, status: ev.paused ? "paused" : "running" };
        default:
          return s;
      }
    });
  }, []);

  const start = useCallback(
    (config: StartConfig) => {
      // 关掉旧连接
      wsRef.current?.close();
      setState({ ...EMPTY, status: "connecting" });

      const proto = location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${location.host}/ws/session`);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: "start", ...config }));
      };
      ws.onmessage = (e) => {
        try {
          handleEvent(JSON.parse(e.data) as ServerEvent);
        } catch {
          /* ignore malformed */
        }
      };
      ws.onerror = () => {
        setState((s) => (s.status === "ended" ? s : { ...s, status: "error", error: "WebSocket 连接错误" }));
      };
      ws.onclose = () => {
        setState((s) =>
          s.status === "running" || s.status === "paused" || s.status === "connecting"
            ? { ...s, status: "ended", endedReason: s.endedReason ?? "disconnected" }
            : s
        );
      };
    },
    [handleEvent]
  );

  const pause = useCallback(() => send({ type: "pause" }), [send]);
  const resume = useCallback(() => send({ type: "resume" }), [send]);
  const stop = useCallback(() => send({ type: "stop" }), [send]);
  const forceSpeaker = useCallback((role: string) => send({ type: "force_speaker", role }), [send]);
  const inject = useCallback((text: string) => send({ type: "inject", text }), [send]);

  const reset = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setState(EMPTY);
  }, []);

  useEffect(() => () => wsRef.current?.close(), []);

  return { state, start, pause, resume, stop, forceSpeaker, inject, reset };
}
