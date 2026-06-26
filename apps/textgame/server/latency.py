"""从 trace JSONL 计算分层时延 + 把扁平 span 还原成树。纯函数，便于单测。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_records(trace_path: str) -> List[Dict[str, Any]]:
    p = Path(trace_path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def _pct(values: List[float], q: float) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return round(s[idx], 2)


def build_tree(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按 parent_id 还原嵌套树；保留 duration/status/attributes。"""
    nodes: Dict[str, Dict[str, Any]] = {}
    for r in records:
        nodes[r["span_id"]] = {
            "span_id": r["span_id"],
            "name": r["name"],
            "duration_ms": r.get("duration_ms"),
            "status": r.get("status"),
            "depth": r.get("depth"),
            "attributes": r.get("attributes", {}),
            "children": [],
        }
    roots: List[Dict[str, Any]] = []
    for r in records:
        node = nodes[r["span_id"]]
        parent_id = r.get("parent_id")
        if parent_id and parent_id in nodes:
            nodes[parent_id]["children"].append(node)
        else:
            roots.append(node)
    return roots


def aggregate(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """分层时延：总/每轮/每角色/bid·speak/LLM p50·p95·max。"""
    total_ms = next((r.get("duration_ms") for r in records if r["name"] == "textgame"), None)

    rounds = sorted(
        (
            {"round": r["attributes"].get("round"), "duration_ms": r.get("duration_ms"),
             "winner": r["attributes"].get("winner")}
            for r in records if r["name"] == "game.round"
        ),
        key=lambda x: (x["round"] is None, x["round"]),
    )

    # 每角色 speak 时延
    per_role: Dict[str, Dict[str, Any]] = {}
    for r in records:
        if r["name"] == "role.speak":
            rid = r["attributes"].get("role", "?")
            d = r.get("duration_ms") or 0
            slot = per_role.setdefault(rid, {"speaks": 0, "total_ms": 0.0})
            slot["speaks"] += 1
            slot["total_ms"] += d
    for rid, slot in per_role.items():
        slot["avg_speak_ms"] = round(slot["total_ms"] / slot["speaks"], 2) if slot["speaks"] else None

    bid_ms = [r.get("duration_ms") or 0 for r in records if r["name"] == "role.bid"]
    speak_ms = [r.get("duration_ms") or 0 for r in records if r["name"] == "role.speak"]
    llm_ms = [
        r["attributes"].get("latency_ms")
        for r in records
        if r["name"] == "llm.call" and r["attributes"].get("latency_ms") is not None
    ]

    def avg(xs: List[float]) -> Optional[float]:
        return round(sum(xs) / len(xs), 2) if xs else None

    return {
        "total_ms": total_ms,
        "rounds": rounds,
        "round_count": len(rounds),
        "avg_round_ms": avg([r["duration_ms"] for r in rounds if r["duration_ms"] is not None]),
        "per_role": per_role,
        "phases": {
            "bid_avg_ms": avg(bid_ms), "bid_count": len(bid_ms),
            "speak_avg_ms": avg(speak_ms), "speak_count": len(speak_ms),
        },
        "llm": {
            "count": len(llm_ms),
            "p50_ms": _pct(llm_ms, 0.50),
            "p95_ms": _pct(llm_ms, 0.95),
            "max_ms": round(max(llm_ms), 2) if llm_ms else None,
        },
    }
