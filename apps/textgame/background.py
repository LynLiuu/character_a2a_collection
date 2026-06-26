"""动态背景导演：把 seed21pro + seedream 两个底座串成「读对话 → 出背景图」的管线。

设计要点（不能拖慢正常对话）：
  - 完全异步：每次生成跑在独立 daemon 线程，对话循环线程只做一次「非阻塞触发」。
  - 单任务：同一时刻最多一个生成在跑；正忙时新的触发直接跳过，保证不堆积。
  - 有延迟没关系：生成完成后才把 background 事件丢回事件队列，前端再淡入贴上去。
  - 上下文 = 当前场景 + 最近对话：seed21pro 只读这段文字来构思画面，
    不需要任何 image 输入（纯文本 → 文生图提示词）。

管线：
  seed21pro.understand(场景 + 最近对话，纯文本) → 一句中文文生图提示词
  → seedream.generate(提示词) → 背景图 url
  → emit({"type": "background", ...})
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional

import seed21pro
import seedcore
import seedream

# 每隔几轮刷新一次背景（开局即第 1 轮先来一张）。
REFRESH_EVERY = 3
# 喂给 seed21pro 的最近对话条数。
RECENT_WINDOW = 6

EmitFn = Callable[[Dict[str, Any]], None]


def build_bg_instruction(scene: str, recent_lines: List[str]) -> str:
    """构造发给 seed21pro 的纯文本指令：让它产出一句 seedream 用的文生图提示词。

    只依据【场景】和【最近对话】两段文字来构思画面，不需要任何图片输入。
    """
    recent = "\n".join(recent_lines) if recent_lines else "（暂无对话，仅依据场景）"
    return (
        "你是一名电影分镜师。请综合下面的【场景】和【最近对话】，"
        "构思此刻最契合剧情走向的画面背景，直接输出一句中文文生图提示词"
        "（只输出提示词本身，不要解释、不要引号）。"
        "提示词要同时体现场景设定与最近对话透露出的氛围/地点变化；"
        "要求：电影感、写实质感、有光影氛围、适合作背景；"
        "不要出现文字、不要人脸特写。\n\n"
        f"【场景】{scene or '未指定'}\n\n"
        f"【最近对话】\n{recent}"
    )


def bg_vision_mock_handler(text: str, image_urls: List[str], meta: Dict[str, Any]) -> str:
    """mock 模式下 seed21pro 的替身：依据 meta 里的场景直接拼一句像样的提示词。"""
    scene = (meta.get("scene") or "").strip()
    base = scene or "一处静谧而富有故事感的场景"
    return f"{base}，电影感氛围，柔和体积光，景深，写实质感，宽幅构图，微尘光束，低饱和冷色调"


class BackgroundDirector:
    """监听事件流、按节奏异步生成动态背景。"""

    def __init__(
        self,
        scene: str,
        emit: EmitFn,
        *,
        vision_client: Optional["seed21pro.Seed21ProClient"] = None,
        image_client: Optional["seedream.SeedreamClient"] = None,
        refresh_every: int = REFRESH_EVERY,
        recent_window: int = RECENT_WINDOW,
        size: str = "2K",
    ) -> None:
        self.scene = scene
        self.emit = emit
        self.refresh_every = max(1, refresh_every)
        self.recent_window = max(1, recent_window)
        self.size = size

        self.vision = vision_client or seed21pro.get_client()
        self.image = image_client or seedream.get_client()
        # mock 模式下给 seed21pro 挂上能产出场景化提示词的替身（seedream 默认 mock 已能出占位图）。
        if self.vision.use_mock:
            self.vision.set_mock_handler(bg_vision_mock_handler)

        self._lock = threading.Lock()
        self._busy = False
        self._stopped = False
        self._seq = 0
        self._recent: List[str] = []

    # --- 事件流入口（对话线程同步调用，必须快速返回） --- #
    def observe(self, event: Dict[str, Any]) -> None:
        etype = event.get("type")
        if etype == "turn":
            name = event.get("name") or event.get("role") or ""
            text = event.get("text") or ""
            self._recent.append(f"{name}：{text}")
            if len(self._recent) > self.recent_window:
                self._recent = self._recent[-self.recent_window :]
        elif etype == "narration":
            self._recent.append(f"【旁白】{event.get('text', '')}")
            if len(self._recent) > self.recent_window:
                self._recent = self._recent[-self.recent_window :]
        elif etype == "round_start":
            rnd = int(event.get("round", 0))
            # 开局（第 1 轮）先出一张，之后每隔 refresh_every 轮刷新一次。
            if rnd >= 1 and (rnd - 1) % self.refresh_every == 0:
                self._trigger(rnd)
        elif etype in ("ended", "error"):
            self.stop()

    def stop(self) -> None:
        self._stopped = True

    # --- 触发与生成 --- #
    def _trigger(self, rnd: int) -> None:
        with self._lock:
            if self._busy or self._stopped:
                return  # 正忙或已结束 → 跳过，保证单任务、不阻塞
            self._busy = True
            self._seq += 1
            seq = self._seq
        snapshot = list(self._recent)
        thread = threading.Thread(
            target=self._generate,
            args=(rnd, seq, snapshot),
            name=f"textgame-bg-{seq}",
            daemon=True,
        )
        thread.start()

    def _generate(self, rnd: int, seq: int, recent_lines: List[str]) -> None:
        try:
            recent = "\n".join(recent_lines)
            with seedcore.trace.start_trace("textgame.background", round=rnd, seq=seq) as t:
                instruction = build_bg_instruction(self.scene, recent_lines)
                vision = self.vision.understand(
                    instruction,
                    image_urls=[],  # 只用文字（场景+最近对话）构思，不喂任何图片
                    trace_span=t,
                    meta={"phase": "bg_prompt", "round": rnd, "scene": self.scene, "recent": recent},
                )
                prompt = (vision.text or "").strip()
                if not prompt:
                    return
                img = self.image.generate(
                    prompt,
                    size=self.size,
                    trace_span=t,
                    meta={"phase": "bg", "round": rnd},
                )
            url = img.url
            if not url or self._stopped:
                return
            self.emit({
                "type": "background",
                "url": url,
                "prompt": prompt,
                "round": rnd,
                "seq": seq,
                "reason": "initial" if rnd == 1 else "refresh",
            })
        except Exception:  # noqa: BLE001 - 背景失败绝不能影响对话
            pass
        finally:
            with self._lock:
                self._busy = False
