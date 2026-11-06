"""Azure AI Speech text-to-speech (REST). Turns the advisor's replies into spoken audio.

Only the assistant's reply text is sent, with any identifiers replaced by placeholders first. No documents,
no KYC data and no owner chat input go to this service."""
from __future__ import annotations

import time
from xml.sax.saxutils import escape

import httpx

from .. import config

LOCALE = {"en": "en-IN", "hi": "hi-IN"}


class TTSUnavailable(Exception):
    pass


class AzureTTS:
    def __init__(self, key: str, region: str, *, timeout: float = 10.0, transport: httpx.BaseTransport | None = None):
        self._key, self._region, self._timeout, self._transport = key, region, timeout, transport

    @property
    def url(self) -> str:
        return f"https://{self._region}.tts.speech.microsoft.com/cognitiveservices/v1"

    def speak(self, text: str, lang: str) -> bytes:
        voice = config.TTS_VOICES.get(lang, config.TTS_VOICES["en"])
        # escape() stops text from closing the tags and injecting its own SSML
        ssml = (f"<speak version='1.0' xml:lang='{LOCALE.get(lang, 'en-IN')}'>"
                f"<voice name='{voice}'><prosody rate='-4%'>{escape(text)}</prosody></voice></speak>")
        headers = {"Ocp-Apim-Subscription-Key": self._key, "Content-Type": "application/ssml+xml",
                   "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3", "User-Agent": "udyvia"}
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as c:
                r = c.post(self.url, content=ssml.encode("utf-8"), headers=headers)
        except httpx.HTTPError as e:
            raise TTSUnavailable(type(e).__name__) from None
        if r.status_code != 200 or not r.content:
            raise TTSUnavailable(f"azure http {r.status_code}")          # never echo the key or the response body
        return r.content


_down_until = 0.0


def get_client() -> AzureTTS | None:
    if not config.AZURE_SPEECH_KEY or time.time() < _down_until:
        return None
    return AzureTTS(config.AZURE_SPEECH_KEY, config.AZURE_SPEECH_REGION)


def configured() -> bool:
    return bool(config.AZURE_SPEECH_KEY)


def mark_down(seconds: float = 30.0) -> None:
    global _down_until
    _down_until = time.time() + seconds
