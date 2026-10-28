"""Stage 2 with the model mocked: no Ollama needed."""
import json

import pytest

from app.extract import ExtractionError, TOOLS, build_messages, extract


def call(name, args):
    return {"tool_calls": [{"function": {"name": name, "arguments": args}}]}


class FakeChat:
    """Returns queued replies and records the messages it was sent."""
    def __init__(self, *replies):
        self.replies = list(replies)
        self.sent = []

    def __call__(self, messages, tools):
        self.sent.append(messages)
        return self.replies.pop(0)


def test_valid_add_entry():
    chat = FakeChat(call("add_entry", {"customer_name": "Ahmed", "amount": 500, "kind": "udhaar"}))
    r = extract("احمد نے 500 کا ادھار لیا", ["Ahmed"], chat=chat)
    assert (r.action, r.customer_name, r.amount, r.kind) == ("add_entry", "Ahmed", 500, "udhaar")
    assert len(chat.sent) == 1


def test_valid_get_balance():
    chat = FakeChat(call("get_balance", {"customer_name": "Ahmed"}))
    r = extract("احمد کا کتنا باقی ہے", ["Ahmed"], chat=chat)
    assert (r.action, r.customer_name, r.amount) == ("get_balance", "Ahmed", None)


def test_arguments_as_json_string_are_accepted():
    args = json.dumps({"customer_name": "Ahmed", "amount": "500", "kind": "payment"})
    r = extract("x", [], chat=FakeChat(call("add_entry", args)))
    assert r.amount == 500 and r.kind == "payment"


def test_invalid_json_then_valid_retries_once():
    chat = FakeChat(call("add_entry", "{not json"),
                    call("add_entry", {"customer_name": "Ahmed", "amount": 5, "kind": "udhaar"}))
    r = extract("x", ["Ahmed"], chat=chat)
    assert r.amount == 5
    assert len(chat.sent) == 2
    assert "invalid" in chat.sent[1][-1]["content"].lower()  # the error is fed back


def test_invalid_twice_raises_clear_error_and_stops():
    bad = call("add_entry", {"customer_name": "Ahmed", "amount": -5, "kind": "udhaar"})
    chat = FakeChat(bad, bad, bad)
    with pytest.raises(ExtractionError, match="say it again"):
        extract("x", ["Ahmed"], chat=chat)
    assert len(chat.sent) == 2  # exactly one retry


@pytest.mark.parametrize("args", [
    {"customer_name": "A", "amount": 0, "kind": "udhaar"},
    {"customer_name": "A", "amount": -1, "kind": "udhaar"},
    {"customer_name": "A", "amount": 12.5, "kind": "udhaar"},
    {"customer_name": "A", "amount": True, "kind": "udhaar"},
    {"customer_name": "A", "amount": "lots", "kind": "udhaar"},
    {"customer_name": "A", "amount": 5, "kind": "gift"},
    {"customer_name": "  ", "amount": 5, "kind": "udhaar"},
    {"amount": 5, "kind": "udhaar"},
])
def test_invalid_arguments_rejected(args):
    chat = FakeChat(call("add_entry", args), call("add_entry", args))
    with pytest.raises(ExtractionError):
        extract("x", ["A"], chat=chat)


def test_no_tool_call_and_unknown_tool_are_invalid():
    chat = FakeChat({"content": "Sure, Ahmed owes 500."}, call("delete_all", {}))
    with pytest.raises(ExtractionError):
        extract("x", [], chat=chat)


def test_unknown_customer_passes_through_for_resolution():
    # Stage 2 may propose a new name; resolution against the ledger happens in the backend.
    chat = FakeChat(call("add_entry", {"customer_name": "زبیر", "amount": 100, "kind": "udhaar"}))
    r = extract("x", ["Ahmed", "Bilal"], chat=chat)
    assert r.customer_name == "زبیر"


def test_prompt_lists_existing_customers_and_forbids_arithmetic():
    system = build_messages("hello", ["Ahmed", "Bilal"])[0]["content"]
    assert "- Ahmed" in system and "- Bilal" in system
    assert "EXACTLY" in system
    assert "Never calculate" in system


def test_tool_schemas_declare_kind_enum_and_positive_amount():
    add = next(t for t in TOOLS if t["function"]["name"] == "add_entry")["function"]["parameters"]
    assert add["properties"]["kind"]["enum"] == ["udhaar", "payment"]
    assert add["properties"]["amount"]["minimum"] == 1


def test_empty_transcript_rejected():
    with pytest.raises(ExtractionError):
        extract("   ", [], chat=FakeChat())
