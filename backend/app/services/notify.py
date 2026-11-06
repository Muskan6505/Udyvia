"""Mock WhatsApp/SMS notification log. Nothing is sent; messages are recorded so the demo can show them.

Privacy: we only ever keep a masked phone number, and message text never contains identifiers (GSTIN,
Udyam, document details), only the order id, amounts and dates."""
from __future__ import annotations

TEMPLATES = {
    "ORDER_CONFIRMED": {
        "en": "Your Accel Business order {oid} is confirmed. Next: e-sign your agreement. Track every step here.",
        "hi": "आपका Accel Business ऑर्डर {oid} कन्फर्म हो गया है। अगला कदम: एग्रीमेंट पर ई-साइन करें। हर स्टेप यहीं ट्रैक करें।"},
    "ESIGNED": {
        "en": "Agreement signed for order {oid}. Next: pay Rs {amount} to start installation.",
        "hi": "ऑर्डर {oid} का एग्रीमेंट साइन हो गया। इंस्टॉलेशन शुरू करने के लिए Rs {amount} का भुगतान करें।"},
    "PAYMENT_FAILED": {
        "en": "Payment for order {oid} didn't go through and nothing was charged. You can retry or pick another method.",
        "hi": "ऑर्डर {oid} का भुगतान पूरा नहीं हुआ और कोई राशि नहीं कटी। आप दोबारा कोशिश करें या दूसरा तरीका चुनें।"},
    "PAYMENT_RECEIVED": {
        "en": "Payment of Rs {amount} received for order {oid}. Installation is being scheduled.",
        "hi": "ऑर्डर {oid} के लिए Rs {amount} का भुगतान मिल गया। इंस्टॉलेशन शेड्यूल हो रहा है।"},
    "INSTALL_SCHEDULED": {
        "en": "Installation for order {oid} is scheduled. Expected completion: {date}.",
        "hi": "ऑर्डर {oid} की इंस्टॉलेशन शेड्यूल हो गई है। संभावित पूर्णता: {date}।"},
    "INSTALLED": {
        "en": "Installation for order {oid} is complete. Your services go live tomorrow.",
        "hi": "ऑर्डर {oid} की इंस्टॉलेशन पूरी हो गई। आपकी सेवाएँ कल से चालू होंगी।"},
    "ACTIVATED": {
        "en": "Your Accel Business services for order {oid} are now active. Welcome aboard!",
        "hi": "ऑर्डर {oid} की आपकी Accel Business सेवाएँ अब चालू हैं। स्वागत है!"},
}


def mask_phone(phone: str | None) -> str | None:
    digits = "".join(c for c in (phone or "") if c.isdigit())
    return None if len(digits) < 4 else "•" * (len(digits) - 4) + digits[-4:]


def render(template: str, language: str, **kw) -> str:
    t = TEMPLATES[template]
    return t.get(language, t["en"]).format(**kw)


def send(log: list[dict], *, template: str, language: str, on: str, phone_masked: str | None, **kw) -> dict:
    """Appends to the order's log. WhatsApp if we have a number, else in-app only."""
    entry = dict(date=on, channel="whatsapp" if phone_masked else "in_app", to=phone_masked,
                 template=template, language=language, text=render(template, language, **kw))
    log.append(entry)
    return entry
