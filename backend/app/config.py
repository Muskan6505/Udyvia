import os
from datetime import date
from pathlib import Path

TODAY = date(2026, 7, 15)  # fixed "today" for all date checks, per the data README
DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# Where inside the catalogue min/max range we price by default.
# Historical bundles sit at a median of 0.47 of the range (mean 0.48).
DEFAULT_PRICE_POSITION = 0.45

# ---- Smart KYC ----
ADDRESS_PROOF_MAX_AGE_DAYS = 90                # README: address proof no older than 90 days
BLUR_MIN_LAPLACIAN_VAR = 100.0                 # specimens: sharp >= 930, blurred K04 ~= 1
MIN_IMAGE_SIDE_PX = 600                        # reject thumbnails
NAME_MATCH_MIN = 88                            # rapidfuzz score (0-100) to call two names "same"
ADDRESS_MATCH_MIN = 92
MAX_GSTIN_OCR_EDITS = 2                        # confusable substitutions tried before giving up


# ---- Advisor LLM ----
def _load_dotenv() -> None:
    """Tiny .env reader (backend/.env, git-ignored). Real environment variables win."""
    f = Path(__file__).resolve().parents[1] / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")     # check the name is current before the demo
ADVISOR_LLM = os.getenv("ADVISOR_LLM", "on")                     # "off" forces the offline extractor
LLM_TIMEOUT_SECONDS = 8.0

# ---- Text to speech (Azure AI Speech) ----
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "centralindia")     # the region your Speech resource was created in
TTS_VOICES = {"en": os.getenv("TTS_VOICE_EN", "en-IN-NeerjaNeural"), "hi": os.getenv("TTS_VOICE_HI", "hi-IN-SwaraNeural")}
TTS_MAX_CHARS = 600
