import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.privacy import audit
from app.services import tts

c = TestClient(app)
GSTIN = "32TTNXB7384T1ZW"


def fake_azure(monkeypatch, handler):
    monkeypatch.setattr(tts, "get_client", lambda: tts.AzureTTS("secret-key", "centralindia", transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(tts, "configured", lambda: True)


def ok(req):
    return httpx.Response(200, content=b"ID3fake-mp3-bytes")


def test_status_reflects_configuration(monkeypatch):
    assert c.get("/voice/status").json() == {"enabled": False}
    fake_azure(monkeypatch, ok)
    assert c.get("/voice/status").json() == {"enabled": True}


def test_disabled_returns_clean_503():
    r = c.post("/voice/speak", json={"text": "hello", "language": "en"})
    assert r.status_code == 503 and "not available" in r.json()["detail"]


def test_speaks_with_right_endpoint_headers_and_voice(monkeypatch):
    seen = {}

    def h(req):
        seen.update(url=str(req.url), key=req.headers["ocp-apim-subscription-key"], ct=req.headers["content-type"],
                    fmt=req.headers["x-microsoft-outputformat"], body=req.content.decode())
        return httpx.Response(200, content=b"ID3audio")

    fake_azure(monkeypatch, h)
    r = c.post("/voice/speak", json={"text": "Total ₹1,777 per month.", "language": "hi"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3audio"
    assert r.headers["cache-control"] == "no-store"
    assert seen["url"] == "https://centralindia.tts.speech.microsoft.com/cognitiveservices/v1"
    assert seen["key"] == "secret-key" and seen["ct"] == "application/ssml+xml" and "mp3" in seen["fmt"]
    assert "hi-IN-SwaraNeural" in seen["body"] and "xml:lang='hi-IN'" in seen["body"]
    r = c.post("/voice/speak", json={"text": "hello", "language": "en"})
    assert "en-IN-NeerjaNeural" in seen["body"]


def test_text_cannot_inject_ssml(monkeypatch):
    seen = {}
    fake_azure(monkeypatch, lambda req: (seen.update(b=req.content.decode()), httpx.Response(200, content=b"x"))[1])
    c.post("/voice/speak", json={"text": "hi</prosody></voice><voice name='evil'>x", "language": "en"})
    assert "<voice name='evil'" not in seen["b"] and "&lt;/voice&gt;" in seen["b"]
    assert seen["b"].count("<voice ") == 1 and seen["b"].count("</voice>") == 1     # only our own tags remain


def test_identifiers_are_redacted_before_leaving(monkeypatch):
    seen = {}
    fake_azure(monkeypatch, lambda req: (seen.update(b=req.content.decode()), httpx.Response(200, content=b"x"))[1])
    c.post("/voice/speak", json={"text": f"Your GSTIN {GSTIN}, call 98765 43210", "language": "en"})
    assert GSTIN not in seen["b"] and "98765" not in seen["b"] and "[GSTIN]" in seen["b"]


def test_audit_records_length_not_text(monkeypatch):
    fake_azure(monkeypatch, ok)
    c.post("/voice/speak", json={"text": "Secret business plan text", "language": "en"})
    ev = [e for e in audit.read_all() if e["event"] == "tts_requested"]
    assert ev and ev[0]["chars"] == 25 and "Secret" not in audit.LOG.read_text()


def test_azure_errors_are_503_and_never_leak_the_key(monkeypatch):
    fake_azure(monkeypatch, lambda req: httpx.Response(401, text="Access denied secret-key"))
    r = c.post("/voice/speak", json={"text": "hello", "language": "en"})
    assert r.status_code == 503 and "secret-key" not in r.text and "401" not in r.text


def test_input_limits_and_validation():
    assert c.post("/voice/speak", json={"text": "", "language": "en"}).status_code == 422
    assert c.post("/voice/speak", json={"text": "x" * 601, "language": "en"}).status_code == 422
    assert c.post("/voice/speak", json={"text": "hello", "language": "fr"}).status_code == 422


def test_policy_discloses_the_speech_service():
    names = [t["name"] for t in c.get("/privacy/policy").json()["third_parties"]]
    assert any("Azure" in n for n in names)
