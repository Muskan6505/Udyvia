from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services import advisor

router = APIRouter(prefix="/advisor", tags=["advisor"])


class MessageIn(BaseModel):
    session_id: str | None = None
    message: str = Field(default="", max_length=2000)
    language: Literal["en", "hi"] = "en"


@router.post("/message")
def message(body: MessageIn):
    s = advisor.get_session(body.session_id, body.language)
    if s is None:
        raise HTTPException(404, "advisor session not found")
    s.lang = body.language
    if body.session_id is None and not body.message.strip():
        # opening turn: just ask the first question
        from ..services import slots as sl
        return dict(session_id=s.id, reply=sl.question("business_type", s.lang), slots=s.slots.model_dump(),
                    missing=sl.missing(s.slots), ready=False, source="offline", quote=None)
    return advisor.handle(s, body.message)
