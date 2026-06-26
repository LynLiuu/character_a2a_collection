from apps.textgame.server.latency import aggregate, build_tree

# 构造一份最小 trace span 记录（模拟 seedcore.trace 落地的 JSONL）
RECORDS = [
    {"span_id": "llm1", "parent_id": "bid1", "name": "llm.call", "duration_ms": 5, "depth": 3,
     "status": "ok", "attributes": {"latency_ms": 5.0}},
    {"span_id": "bid1", "parent_id": "r1", "name": "role.bid", "duration_ms": 6, "depth": 2,
     "status": "ok", "attributes": {"role": "alice"}},
    {"span_id": "spk1", "parent_id": "r1", "name": "role.speak", "duration_ms": 20, "depth": 2,
     "status": "ok", "attributes": {"role": "alice"}},
    {"span_id": "r1", "parent_id": "root", "name": "game.round", "duration_ms": 30, "depth": 1,
     "status": "ok", "attributes": {"round": 1, "winner": "alice"}},
    {"span_id": "spk2", "parent_id": "r2", "name": "role.speak", "duration_ms": 40, "depth": 2,
     "status": "ok", "attributes": {"role": "bob"}},
    {"span_id": "r2", "parent_id": "root", "name": "game.round", "duration_ms": 50, "depth": 1,
     "status": "ok", "attributes": {"round": 2, "winner": "bob"}},
    {"span_id": "root", "parent_id": None, "name": "textgame", "duration_ms": 90, "depth": 0,
     "status": "ok", "attributes": {"roles": ["alice", "bob"]}},
]


def test_build_tree_nesting():
    roots = build_tree(RECORDS)
    assert len(roots) == 1
    root = roots[0]
    assert root["name"] == "textgame"
    round_names = [c["name"] for c in root["children"]]
    assert round_names == ["game.round", "game.round"]
    r1 = root["children"][0]
    assert {c["name"] for c in r1["children"]} == {"role.bid", "role.speak"}


def test_aggregate_layers():
    agg = aggregate(RECORDS)
    assert agg["total_ms"] == 90
    assert agg["round_count"] == 2
    assert agg["per_role"]["alice"]["speaks"] == 1
    assert agg["per_role"]["bob"]["avg_speak_ms"] == 40
    assert agg["phases"]["speak_count"] == 2
    assert agg["phases"]["bid_count"] == 1
    assert agg["llm"]["count"] == 1
    assert agg["llm"]["p50_ms"] == 5.0
