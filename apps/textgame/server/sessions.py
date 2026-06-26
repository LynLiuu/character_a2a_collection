"""对话记录落盘与读取：sessions/{id}.json。"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# 对话记录落在 textgame app 目录下，与 trace 同源，整个 app 自包含。
SESSIONS_DIR = Path(__file__).resolve().parents[1] / "sessions"


def _dir() -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR


def save_session(
    session_id: str,
    config: Dict[str, Any],
    turns: List[Dict[str, Any]],
    ended: Dict[str, Any],
) -> Dict[str, Any]:
    trace_path = ended.get("trace_path")
    rec = {
        "id": session_id,
        "created": time.time(),
        "scene": config.get("scene", ""),
        "roles": config.get("roles", []),
        "max_rounds": config.get("max_rounds"),
        "reason": ended.get("reason"),
        "trace_path": trace_path,
        "trace_id": Path(trace_path).stem if trace_path else None,
        "total_turns": len(turns),
        "turns": [
            {
                "round": t.get("round"),
                "role": t.get("role"),
                "name": t.get("name"),
                "text": t.get("text"),
                "latency_ms": t.get("latency_ms"),
            }
            for t in turns
        ],
    }
    (_dir() / f"{session_id}.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return rec


def list_sessions() -> List[Dict[str, Any]]:
    out = []
    paths = sorted(_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in paths:
        d = json.loads(p.read_text(encoding="utf-8"))
        out.append({k: d.get(k) for k in ("id", "created", "scene", "roles", "total_turns", "reason", "trace_id")})
    return out


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    path = _dir() / f"{session_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
