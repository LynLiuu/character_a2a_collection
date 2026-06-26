"""WebSocket：一条连接跑一局可控对话。

客户端→服务端: start / pause / resume / stop / force_speaker / inject
服务端→客户端: session / round_start / bid / pick / turn / narration / round_end / ended / error / state
"""
from __future__ import annotations

import asyncio
import queue
import uuid
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

import seedcore

from ..mock import demo_mock_handler
from ..session import WsController, run_session_in_thread
from .sessions import save_session

router = APIRouter()


@router.websocket("/ws/session")
async def ws_session(ws: WebSocket) -> None:
    await ws.accept()
    loop = asyncio.get_event_loop()
    out_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
    controller = WsController()

    # 没有真实 key/ep 时挂上 demo mock，保证前端可完整体验
    client = seedcore.get_client()
    if client.use_mock:
        client.set_mock_handler(demo_mock_handler)

    state: Dict[str, Any] = {"thread": None, "config": None, "turns": [], "id": uuid.uuid4().hex}
    forward_task = None

    async def forward() -> None:
        """把后台线程的事件队列转发到 WS；结束时落盘会话。"""
        while True:
            event = await loop.run_in_executor(None, out_queue.get)
            if event.get("type") == "turn":
                state["turns"].append(event)
            try:
                await ws.send_json(event)
            except Exception:
                return
            if event.get("type") in ("ended", "error"):
                if state["config"] is not None:
                    save_session(state["id"], state["config"], state["turns"], event)
                return

    try:
        while True:
            msg = await ws.receive_json()
            mtype = msg.get("type")

            if mtype == "start":
                if state["thread"] is not None:
                    await ws.send_json({"type": "error", "msg": "本连接已开始过一局"})
                    continue
                state["config"] = {
                    "roles": msg.get("roles", []),
                    "scene": msg.get("scene", ""),
                    "max_rounds": msg.get("max_rounds", None),
                }
                await ws.send_json({"type": "session", "id": state["id"]})
                forward_task = asyncio.create_task(forward())
                state["thread"] = run_session_in_thread(state["config"], out_queue, controller)

            elif mtype == "pause":
                controller.pause()
                await ws.send_json({"type": "state", "paused": True})
            elif mtype == "resume":
                controller.resume()
                await ws.send_json({"type": "state", "paused": False})
            elif mtype == "stop":
                controller.stop()
            elif mtype == "force_speaker":
                controller.force_speaker(msg.get("role"))
            elif mtype == "inject":
                controller.inject(msg.get("text", ""))
            else:
                await ws.send_json({"type": "error", "msg": f"未知指令: {mtype}"})

    except WebSocketDisconnect:
        pass
    finally:
        controller.stop()
        if forward_task is not None:
            try:
                await asyncio.wait_for(forward_task, timeout=5)
            except Exception:
                pass
