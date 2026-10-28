"""Stage 2: Urdu transcript -> validated tool call (add_entry / get_balance).

The model only chooses the action and fills in arguments. It never computes balances.
"""
import json
from typing import Callable, Optional

import httpx
from pydantic import ValidationError

from .config import Settings
from .schemas import AddEntryArgs, Extraction, GetBalanceArgs

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_entry",
            "description": "Record one ledger entry: either credit given to a customer (udhaar) "
                           "or money received from a customer (payment).",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string",
                                      "description": "Exactly one of the existing customer names, "
                                                     "or a new name written in Urdu script."},
                    "amount": {"type": "integer", "minimum": 1,
                               "description": "Whole rupees, positive."},
                    "kind": {"type": "string", "enum": ["udhaar", "payment"],
                             "description": "udhaar = customer took goods on credit; "
                                            "payment = customer paid money back."},
                    "note": {"type": "string", "description": "Optional short note."},
                },
                "required": ["customer_name", "amount", "kind"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_balance",
            "description": "Look up how much a customer currently owes. Use when the shopkeeper asks.",
            "parameters": {
                "type": "object",
                "properties": {"customer_name": {"type": "string"}},
                "required": ["customer_name"],
            },
        },
    },
]

SYSTEM_PROMPT = """You turn a shopkeeper's spoken Urdu (already transcribed) into exactly one tool call.

Tools:
- add_entry: the shopkeeper records udhaar (customer took goods on credit, e.g. "ne 500 ka udhaar liya")
  or payment (customer paid money, e.g. "ne 200 diye", "ne 200 wapas kiye").
- get_balance: the shopkeeper asks how much a customer owes (e.g. "ka kitna baqi hai?").

Rules:
- Call exactly one tool. Do not answer in prose.
- Never calculate balances or totals. The database does that.
- customer_name: the existing customers are listed below. If the spoken name is one of them,
  copy it EXACTLY as listed. If it is clearly not any of them, use the new name written in Urdu script.
  Do not invent a different spelling of an existing customer.
- amount must be a positive whole number in rupees.
- kind must be "udhaar" or "payment".

Existing customers:
{names}
"""


class ExtractionError(Exception):
    pass


# chat(messages, tools) -> the assistant message dict, e.g. {"tool_calls": [...]}
ChatFn = Callable[[list[dict], list[dict]], dict]


def ollama_chat(settings: Settings) -> ChatFn:
    def chat(messages: list[dict], tools: list[dict]) -> dict:
        payload = {"model": settings.model_name, "messages": messages, "tools": tools,
                   "stream": False, "options": {"temperature": 0}}
        try:
            r = httpx.post(f"{settings.ollama_url}/api/chat", json=payload,
                           timeout=settings.model_timeout)
            r.raise_for_status()
            return r.json()["message"]
        except httpx.ConnectError:
            raise ExtractionError(f"Cannot reach Ollama at {settings.ollama_url}. "
                                  "Is `ollama serve` running?")
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise ExtractionError(f"Unexpected response from Ollama: {e}")
    return chat


def build_messages(transcript: str, names: list[str]) -> list[dict]:
    listed = "\n".join(f"- {n}" for n in names) if names else "(none yet)"
    return [
        {"role": "system", "content": SYSTEM_PROMPT.format(names=listed)},
        {"role": "user", "content": transcript},
    ]


def parse_message(message: dict) -> Extraction:
    """Validate one assistant message. Raises ValueError with a model-readable reason."""
    calls = message.get("tool_calls") or []
    if not calls:
        raise ValueError("You did not call a tool. Call add_entry or get_balance.")
    fn = calls[0].get("function") or {}
    name, args = fn.get("name"), fn.get("arguments", {})
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            raise ValueError("Tool arguments were not valid JSON.")
    if not isinstance(args, dict):
        raise ValueError("Tool arguments must be a JSON object.")
    try:
        if name == "add_entry":
            a = AddEntryArgs(**args)
            return Extraction(action="add_entry", customer_name=a.customer_name,
                              amount=a.amount, kind=a.kind, note=a.note)
        if name == "get_balance":
            b = GetBalanceArgs(**args)
            return Extraction(action="get_balance", customer_name=b.customer_name)
    except (ValidationError, TypeError) as e:
        if isinstance(e, ValidationError):
            problems = "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())
        else:
            problems = str(e)
        raise ValueError(f"Invalid arguments for {name}: {problems}")
    raise ValueError(f"Unknown tool {name!r}. Use add_entry or get_balance.")


def extract(transcript: str, names: list[str], chat: Optional[ChatFn] = None,
            settings: Optional[Settings] = None) -> Extraction:
    """Ask the model for a tool call; on invalid output retry once, then fail clearly."""
    if not transcript.strip():
        raise ExtractionError("The transcript is empty.")
    chat = chat or ollama_chat(settings or Settings.from_env())
    messages = build_messages(transcript, names)
    last_error = ""
    for attempt in range(2):
        reply = chat(messages, TOOLS)
        try:
            return parse_message(reply)
        except ValueError as e:
            last_error = str(e)
            messages = messages + [
                {"role": "assistant", "content": reply.get("content") or "",
                 "tool_calls": reply.get("tool_calls") or []},
                {"role": "user", "content": f"That was invalid: {last_error} Try again."},
            ]
    raise ExtractionError(f"Could not understand the request after retrying ({last_error}). "
                          "Please say it again.")
