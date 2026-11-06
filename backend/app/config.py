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
