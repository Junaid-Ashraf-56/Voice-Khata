"""End-to-end through FastAPI with stage 1 and the model mocked."""
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.transcribe import TranscribeError


class FakeTranscriber:
    def __init__(self, text="transcript"):
        self.text = text

    def transcribe(self, wav):
        return self.text


def tool(name, args):
    return {"tool_calls": [{"function": {"name": name, "arguments": args}}]}


def make_client(reply, transcriber=None):
    app = create_app(Settings(db_path=":memory:"),
                     transcriber=transcriber or FakeTranscriber(),
                     chat=lambda m, t: reply,
                     to_wav=lambda b: b"WAV")
    return TestClient(app)


def upload(client):
    return client.post("/api/process", files={"file": ("a.webm", b"fake", "audio/webm")})


def test_nothing_is_written_until_confirm():
    c = make_client(tool("add_entry", {"customer_name": "Ahmed", "amount": 500, "kind": "udhaar"}))
    r = upload(c)
    assert r.status_code == 200
    p = r.json()["proposal"]
    assert p["is_new_customer"] is True
    assert c.get("/api/customers").json() == []          # still empty

    done = c.post("/api/confirm", json={"proposal_id": p["id"]})
    assert done.status_code == 200 and done.json()["balance"] == 500
    assert c.get("/api/customers").json() == [{"name": "Ahmed", "balance": 500}]


def test_confirm_twice_or_unknown_id_fails():
    c = make_client(tool("add_entry", {"customer_name": "Ahmed", "amount": 5, "kind": "udhaar"}))
    pid = upload(c).json()["proposal"]["id"]
    assert c.post("/api/confirm", json={"proposal_id": pid}).status_code == 200
    assert c.post("/api/confirm", json={"proposal_id": pid}).status_code == 404
    assert c.post("/api/confirm", json={"proposal_id": "bogus"}).status_code == 404
    assert c.get("/api/customers").json()[0]["balance"] == 5   # not double-counted


def test_get_balance_uses_sql_and_writes_nothing():
    replies = iter([
        tool("add_entry", {"customer_name": "Ahmed", "amount": 500, "kind": "udhaar"}),
        tool("add_entry", {"customer_name": "ahmed", "amount": 200, "kind": "payment"}),
        tool("get_balance", {"customer_name": "Ahmed"}),
    ])
    app = create_app(Settings(db_path=":memory:"), transcriber=FakeTranscriber(),
                     chat=lambda m, t: next(replies), to_wav=lambda b: b"WAV")
    c = TestClient(app)
    for _ in range(2):
        pid = upload(c).json()["proposal"]["id"]
        c.post("/api/confirm", json={"proposal_id": pid})
    b = upload(c).json()["balance"]
    assert b == {"customer_name": "Ahmed", "found": True, "balance": 300, "similar_names": []}
    assert len(c.get("/api/customers").json()) == 1  # "ahmed" reused "Ahmed"


def test_get_balance_for_unknown_customer_does_not_create_one():
    c = make_client(tool("get_balance", {"customer_name": "Zubair"}))
    b = upload(c).json()["balance"]
    assert b["found"] is False
    assert c.get("/api/customers").json() == []


def test_invalid_model_output_returns_clear_error():
    c = make_client(tool("add_entry", {"customer_name": "A", "amount": -1, "kind": "udhaar"}))
    r = upload(c)
    assert r.status_code == 422 and "say it again" in r.json()["detail"]


def test_transcribe_error_is_reported():
    class Broken:
        def transcribe(self, wav):
            raise TranscribeError("Cannot reach Ollama")
    r = upload(make_client({}, transcriber=Broken()))
    assert r.status_code == 422 and "Ollama" in r.json()["detail"]


def test_audio_error_is_400():
    from app.audio import AudioError

    def bad(_):
        raise AudioError("bad audio")
    app = create_app(Settings(db_path=":memory:"), transcriber=FakeTranscriber(),
                     chat=lambda m, t: {}, to_wav=bad)
    assert upload(TestClient(app)).status_code == 400
