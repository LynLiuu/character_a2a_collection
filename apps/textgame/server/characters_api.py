"""人设卡 CRUD REST。读写 apps/textgame/characters/ 目录。"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..store import (
    CardError,
    delete_persona,
    get_persona,
    list_personas,
    upsert_persona,
)

router = APIRouter(prefix="/api/characters", tags=["characters"])


class CardIn(BaseModel):
    id: str
    name: str
    persona: str = ""
    goals: List[str] = Field(default_factory=list)
    speaking_style: str = ""
    assertiveness: float = 0.5
    avatar: Optional[str] = None
    color: Optional[str] = None


@router.get("")
def api_list():
    return [p.to_dict() for p in list_personas()]


@router.get("/{cid}")
def api_get(cid: str):
    try:
        return get_persona(cid).to_dict()
    except CardError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("", status_code=201)
def api_create(card: CardIn):
    try:
        return upsert_persona(card.model_dump(), must_be_new=True).to_dict()
    except CardError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{cid}")
def api_update(cid: str, card: CardIn):
    data = card.model_dump()
    data["id"] = cid  # 路径为准，防止改 id
    try:
        return upsert_persona(data, must_exist=True).to_dict()
    except CardError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{cid}", status_code=204)
def api_delete(cid: str):
    try:
        delete_persona(cid)
    except CardError as e:
        raise HTTPException(status_code=404, detail=str(e))
