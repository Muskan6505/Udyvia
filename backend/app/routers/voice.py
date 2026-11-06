from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .. import config
from ..privacy import audit
from ..privacy.masking import scrub
from ..services import tts

router = APIRouter(prefix="/voice", tags=["voice"])


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=config.TTS_MAX_CHARS)
    language: Literal["en", "hi"] = "en"


@router.get("/status")
def status():
    """Lets the UI hide the speaker buttons when speech isn't configured."""
    return {"enabled": tts.configured()}


@router.post("/speak")
def speak(body: SpeakIn):
    client = tts.get_client()
    if client is None:
        raise HTTPException(503, "Voice is not available right now.")
    safe = scrub(body.text, "redact")                 # identifiers never go to the speech service
    try:
        audio = client.speak(safe, body.language)
    except tts.TTSUnavailable:
        tts.mark_down()
        audit.log("tts_failed", None, language=body.language)
        raise HTTPException(503, "Voice is not available right now.") from None
    audit.log("tts_requested", None, language=body.language, chars=len(safe))     # length only, never the text
    return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})
