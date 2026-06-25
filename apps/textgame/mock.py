"""文游 demo 的 mock 响应器：没有真实方舟 key 时也能跑出一局像样的对话。

注入方式：
    client = seedcore.get_client(mock_handler=demo_mock_handler)

真实 key 到位后去掉 mock_handler 即走真实方舟调用，上层代码无需改动。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from seedcore import Message


def _stable_hash(s: str) -> int:
    h = 0
    for c in s:
        h = (h * 31 + ord(c)) % 100000
    return h


# 每个角色按轮次预设的台词与抢麦倾向，纯本地、可复现。
_LINES = {
    "alice": [
        "这口井看着就有古怪，我先下去探探？",
        "别拦我！时间不等人，再磨蹭天就黑了。",
        "你们听，井底好像有水声……是不是有路？",
        "好吧好吧，那我们一起，但绳子得系紧点。",
    ],
    "bob": [
        "且慢。老话说『深井无声，落者无影』，不可贸然。",
        "我熟悉这片林子，先看看井沿有没有机关。",
        "安全第一，爱丽丝，你的胆子总有一天会害了大家。",
    ],
    "cara": [
        "……井壁上有新刮的痕迹。有人比我们先到。",
        "别吵，听见没——那不是水声，是脚步。",
    ],
}

_INTENTS = {
    "alice": "催促大家赶紧行动、自告奋勇下井",
    "bob": "提醒风险、主张先检查再行动",
    "cara": "指出一个被忽略的关键线索",
}


def demo_mock_handler(messages: List[Message], meta: Dict[str, Any]) -> str:
    role = meta.get("role", "")
    rnd = int(meta.get("round", 1))
    phase = meta.get("phase", "")

    if phase == "bid":
        # 用稳定 hash 让意愿在轮次间有起伏，但可复现
        base = {"alice": 7, "bob": 5, "cara": 3}.get(role, 5)
        jitter = _stable_hash(f"{role}-{rnd}") % 4  # 0~3
        eagerness = min(10, base + jitter)
        intent = _INTENTS.get(role, "想发表看法")
        return json.dumps({"eagerness": eagerness, "intent": intent}, ensure_ascii=False)

    if phase == "speak":
        lines = _LINES.get(role, ["……"])
        idx = (rnd - 1) % len(lines)
        return lines[idx]

    return "[mock]"
