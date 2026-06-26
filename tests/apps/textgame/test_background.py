"""动态背景导演测试：mock 下端到端产出 background 事件，且单任务/不阻塞。"""
import queue
import time

import seed21pro
import seedream
from apps.textgame.background import (
    BackgroundDirector,
    bg_vision_mock_handler,
    build_bg_instruction,
)


def _wait_for_bg(q: "queue.Queue", timeout: float = 5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            ev = q.get(timeout=timeout)
        except queue.Empty:
            break
        if ev.get("type") == "background":
            return ev
    return None


def _fresh_director(scene: str, emit) -> BackgroundDirector:
    # 强制刷新两个底座单例，确保拿到 mock 客户端
    seedream.get_client(reload=True)
    seed21pro.get_client(reload=True)
    return BackgroundDirector(scene, emit=emit, refresh_every=3, recent_window=4)


def test_build_instruction_includes_scene_and_recent():
    instr = build_bg_instruction("古井旁的夜晚", ["alice：我先下去", "bob：且慢"])
    assert "古井旁的夜晚" in instr
    assert "alice：我先下去" in instr and "bob：且慢" in instr
    assert "文生图提示词" in instr


def test_vision_mock_handler_uses_scene():
    out = bg_vision_mock_handler("instr", [], {"scene": "雪山脚下的木屋"})
    assert "雪山脚下的木屋" in out


def test_initial_background_emitted_on_round1():
    q: "queue.Queue" = queue.Queue()
    d = _fresh_director("末日列车", emit=q.put)
    d.observe({"type": "round_start", "round": 1})
    ev = _wait_for_bg(q)
    assert ev is not None
    assert ev["url"] and ev["reason"] == "initial"
    assert "末日列车" in ev["prompt"]  # mock 提示词带上了场景


def test_recent_dialogue_feeds_into_prompt():
    q: "queue.Queue" = queue.Queue()
    d = _fresh_director("", emit=q.put)
    d.observe({"type": "turn", "round": 1, "name": "卡拉", "text": "井壁上有新刮的痕迹"})
    assert any("卡拉：井壁上有新刮的痕迹" in line for line in d._recent)


def test_recent_window_caps_length():
    d = _fresh_director("", emit=lambda e: None)
    for i in range(10):
        d.observe({"type": "turn", "round": i, "name": f"r{i}", "text": "x"})
    assert len(d._recent) == 4  # recent_window


def test_single_task_no_overlap_while_busy():
    q: "queue.Queue" = queue.Queue()
    d = _fresh_director("场景", emit=q.put)
    # 人为占用：标记 busy 后再次触发应被跳过
    d._busy = True
    d._trigger(1)
    time.sleep(0.2)
    assert q.empty()  # 正忙 → 不产生新任务


def test_only_refresh_on_interval_rounds():
    triggered = []
    d = _fresh_director("场景", emit=lambda e: None)
    # 替换 _trigger 记录被触发的轮次
    d._trigger = lambda rnd: triggered.append(rnd)  # type: ignore[method-assign]
    for rnd in range(1, 8):
        d.observe({"type": "round_start", "round": rnd})
    # refresh_every=3：第 1、4、7 轮触发
    assert triggered == [1, 4, 7]


def test_stop_prevents_further_triggers():
    q: "queue.Queue" = queue.Queue()
    d = _fresh_director("场景", emit=q.put)
    d.stop()
    d.observe({"type": "round_start", "round": 1})
    time.sleep(0.2)
    assert q.empty()
