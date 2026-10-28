# Architecture

```
 Browser (web/)                      FastAPI backend (app/)                       Ollama / local
 ──────────────                      ──────────────────────                       ──────────────
 MediaRecorder
   webm/opus ──POST /api/process──▶  audio.py      ffmpeg → 16 kHz mono WAV
                                       │
                                       ▼
                                     transcribe.py  STAGE 1  WAV ───────────────▶ Gemma (audio in)
                                       │            Urdu-script transcript ◀─────  (or faster-whisper)
                                       ▼
                                     extract.py     STAGE 2  transcript + names ─▶ Gemma (tool calling)
                                       │            add_entry / get_balance ◀────
                                       ▼            validated by schemas.py (Pydantic)
                                     ledger.resolve_name   existing name or NEW
                                       │
                 ┌─────────────────────┴───────────────────────┐
           get_balance                                     add_entry
                 │                                               │
   ledger.balance() (SQL SUM)                     held in memory as a Proposal (10 min TTL)
   answer returned, nothing written                              │
                                       ◀── proposal shown ───────┘
 user taps Confirm ──POST /api/confirm──▶  the ONLY route that calls Ledger.add_entry
```

## Design decisions

**Two separate stages.** `transcribe.py` (audio → text) and `extract.py` (text → tool call) share
no code. Stage 1 can be swapped (`TRANSCRIBE_BACKEND=whisper`) without touching stage 2, and each
stage can be tested and debugged alone. A bad transcript is visible to the user before anything is saved.

**ffmpeg normalisation in the backend.** Browsers record webm/opus; the model path wants 16 kHz mono
WAV. `audio.py` converts with temp files rather than pipes, because ffmpeg cannot seek a pipe to
write WAV header sizes.

**The model never does arithmetic.** It only picks an action and fills arguments. Balances come from
`SUM(CASE kind WHEN 'udhaar' THEN amount ELSE -amount END)` in SQLite. Positive = customer owes the
shopkeeper; negative = overpaid.

**Confirmation is enforced server-side.** `/api/process` never writes. For `add_entry` it stores a
`Proposal` in server memory and returns an id. Only `/api/confirm` writes, and it writes the
server-held values, so a client cannot alter the amount or name at confirm time. IDs are single-use and
expire after 10 minutes. Pending proposals are lost on restart (by design: unconfirmed means unsaved).
`get_balance` is read-only and needs no confirmation.

**Validation + one retry.** Every tool call is parsed through Pydantic (`amount` positive integer,
`kind` in `udhaar|payment`, non-empty name). Invalid output triggers exactly one retry with the error
message fed back to the model; a second failure returns HTTP 422 with a plain message. SQLite `CHECK`
constraints are a last line of defence.

**Name resolution.** Stage 2 gets the list of existing names and is told to copy one exactly or give a
new name in Urdu script. The backend does not trust that: `ledger.resolve_name` matches ignoring case
and whitespace, and otherwise treats the name as new. Near matches (difflib, cutoff 0.75) are shown as
hints only and never merged automatically, since attaching a debt to the wrong person is worse than
an extra confirmation look.

**Dependency injection.** `create_app(settings, transcriber, chat, to_wav)` lets the test suite replace
ffmpeg, stage 1 and the model, so tests run offline.

**Single user, no auth, no deployment.** Out of scope for the Hack Day.
