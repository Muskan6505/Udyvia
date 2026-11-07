from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import auth
from ..services import advisor

router = APIRouter(prefix="/advisor", tags=["advisor"])


class MessageIn(BaseModel):
    session_id: str | None = None
    message: str = Field(default="", max_length=2000)
    language: Literal["en", "hi"] = "en"


@router.post("/message")
def message(body: MessageIn, user: dict | None = Depends(auth.optional_user)):
    s = advisor.get_session(body.session_id, body.language)
    if s is None:
        raise HTTPException(404, "advisor session not found")
    if user and s.user_id is None:
        s.user_id = user["id"]
    if s.user_id and (not user or user["id"] != s.user_id):
        raise HTTPException(404, "advisor session not found")
    s.lang = body.language
    if body.session_id is None and not body.message.strip():
        # opening turn: just ask the first question
        from ..services import slots as sl
        return dict(session_id=s.id, reply=sl.question("business_type", s.lang), slots=s.slots.model_dump(),
                    missing=sl.missing(s.slots), ready=False, source="offline", quote=None)
    return advisor.handle(s, body.message)
