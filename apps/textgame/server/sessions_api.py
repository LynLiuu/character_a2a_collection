"""会话记录 / trace 树 / 分层时延 REST。"""
from fastapi import APIRouter, HTTPException

from .latency import aggregate, build_tree, load_records
from .sessions import get_session, list_sessions

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
def api_list():
    return list_sessions()


@router.get("/{sid}")
def api_get(sid: str):
    rec = get_session(sid)
    if rec is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return rec


@router.get("/{sid}/trace")
def api_trace(sid: str):
    rec = get_session(sid)
    if rec is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    records = load_records(rec.get("trace_path") or "")
    return {"trace_id": rec.get("trace_id"), "tree": build_tree(records)}


@router.get("/{sid}/latency")
def api_latency(sid: str):
    rec = get_session(sid)
    if rec is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    records = load_records(rec.get("trace_path") or "")
    return aggregate(records)
