"""FastAPI 应用装配：路由 + CORS + 生产模式静态托管前端。"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from seedcore import get_config, is_mock

from . import characters_api, sessions_api, ws

# textgame 的运行产物都落在本 app 目录下（trace 用绝对路径，避免受启动 CWD 影响）。
_APP_DIR = Path(__file__).resolve().parents[1]
get_config().trace.dir = str(_APP_DIR / "traces")

app = FastAPI(title="Seed Character 文游", version="0.1.0")

# 开发期前端在 :5173，放开 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(characters_api.router)
app.include_router(sessions_api.router)
app.include_router(ws.router)


@app.get("/api/health")
def health():
    cfg = get_config()
    return {"ok": True, "mock": is_mock(cfg), "model": cfg.defaults.model}


# 生产模式：若已 `npm run build`，直接托管 frontend/dist（放最后，避免吃掉 API 路由）
_DIST = _APP_DIR / "frontend" / "dist"
if _DIST.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
