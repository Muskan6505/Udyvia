"""Single source of truth for retention periods. The consent notice, /privacy/policy and the cleanup job
all read these, so what we tell people is what the code enforces."""
KYC_HOURS = 24            # uploaded document images, OCR results and the KYC decision
ADVISOR_HOURS = 24        # chat slots (may include a GSTIN the owner typed)
QUOTE_HOURS = 72          # quotes that never became an order
ORDER_DAYS = 30           # demo orders; a real deployment keeps contracts for the legal period instead
LEAD_DAYS = 90            # saved progress of an account that has been inactive and never became a customer
SESSION_DAYS = 7          # sign-in sessions
PURGE_INTERVAL_SECONDS = 600

THIRD_PARTIES = [
    {"name": "Gemini (Google)", "purpose": "Reads the owner's chat answers into fields and phrases the bundle explanation",
     "receives": "Chat text with GSTIN, Udyam, phone, email and 12-digit ID numbers replaced by placeholders",
     "never_receives": ["document images", "OCR text", "KYC results"]},
    {"name": "Azure AI Speech (Microsoft)", "purpose": "Reads the advisor's replies aloud when the owner taps Listen or turns on read-aloud",
     "receives": "The advisor's reply text only, with identifiers replaced by placeholders. We keep only a length count",
     "never_receives": ["the owner's own messages", "document images", "KYC results"]},
]
