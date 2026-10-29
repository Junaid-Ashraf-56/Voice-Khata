# Voice Khata

An Urdu voice ledger for shopkeepers. Say *"Ahmed ne 500 ka udhaar liya"* and it proposes a ledger
entry; say *"Ahmed ka kitna baqi hai?"* and it tells you the balance. Everything runs locally: audio
and ledger data never leave your machine.

Built for the Hacktoberfest Hack Day (Sahiwal × Zeppelin Labs), 2026.

## Features

- Record from the browser, speak in Urdu.
- Two-stage AI pipeline: audio → Urdu transcript → `add_entry` / `get_balance` tool call.
- **You confirm before anything is saved.** The server enforces this; the UI is not the only guard.
- Balances computed by SQL `SUM`, never by the model.
- Model output validated (positive integer amounts, kind `udhaar` or `payment`) with one retry, then a clear error.
- Existing customer names are given to the model; it must pick one exactly or propose a new name.
  Near matches (e.g. Ahmed / Ahmad) are flagged, never merged silently.
- Local-only: Gemma via Ollama; optional faster-whisper for stage 1.

### Interface

- Single page, plain HTML/CSS/JS (no framework), dark theme, works at phone width.
- Mic button with a live waveform and timer while recording.
- Confirmation card showing what was heard, the amount, udhaar/payment, the customer, and a **NEW** badge
  for customers not yet in the ledger.
- Customer list with balances colour-coded as *owes you*, *you owe* or *settled*.
- Friendly error cards. When the request can't be understood, the card shows the transcript, so you can
  tell whether the audio was misheard (stage 1) or misunderstood (stage 2). The raw error is under
  "Technical details".
- Urdu text is rendered in Noto Nastaliq Urdu (loaded from Google Fonts; without internet it falls back
  to a system font and everything else still works).

## Setup

Requirements: Python 3.10+, [ffmpeg](https://ffmpeg.org/), [Ollama](https://ollama.com/), make, and a
browser with microphone access (Chrome, Edge or Firefox).

```bash
git clone <this repo> voice-khata && cd voice-khata

# 1. System tools (Ubuntu/Debian; use your OS's package manager otherwise)
sudo apt install ffmpeg python3-venv make

# 2. Model (about 6.6 GB download)
ollama serve &                  # skip if Ollama already runs as a service
ollama pull gemma4:e4b
ollama list                     # the tag shown here must match MODEL_NAME

# 3. App
cp .env.example .env            # optional; defaults work with the tag above
make run                        # creates .venv, installs deps, serves http://127.0.0.1:8000
```

Open <http://localhost:8000> (the microphone needs `localhost` or HTTPS), tap the mic, speak, tap again
to stop, then **Confirm & save** or **Discard**.

The first request after starting Ollama is slow while the model loads into memory.

### Tests (offline, model mocked, Ollama not needed)

```bash
make test
```

42 tests. One audio test is skipped automatically if ffmpeg is not installed.

### If Gemma's Urdu transcription is weak

Stage 1 can use faster-whisper instead. Uncomment `faster-whisper` in `requirements.txt`, reinstall
(`make setup`), and set `TRANSCRIBE_BACKEND=whisper` and `WHISPER_MODEL=<an Urdu-capable model>` in `.env`.
Stage 2 still uses Gemma. (The whisper path has not been tested yet.)

## How AI is used

**Inside the product** (open-source, run locally):
- **Gemma 4 E4B via Ollama**, stage 1: turns the recorded audio into an Urdu-script transcript.
  The prompt asks for Urdu script and forbids translation.
- **Gemma 4 E4B via Ollama**, stage 2: reads the transcript plus the list of existing customers and
  makes a function call (`add_entry` or `get_balance`). It does not compute balances; SQLite does.
- **faster-whisper** (optional): drop-in replacement for stage 1.
- The model's output is untrusted: it is validated with Pydantic, and a human confirms before saving.

**To build it:** AI coding tools (Claude Code) helped write and review the code, tests, UI and docs in
this repository. I reviewed and ran the result.

See [docs/architecture.md](docs/architecture.md) for the design.

## Test results

### Environment it was run on

- Linux (Ubuntu), one machine
- Ollama 0.40.13, model `gemma4:e4b` (Q4_K_M, 6.58 GB, reports `audio` and `tools` capabilities)
- ffmpeg 6.1.1, Python 3.12

### What has been checked

- `make test`: 42 passed.
- The full browser path runs: webm recording → ffmpeg → Gemma transcription → Gemma tool call → confirm card.
- Stage 2 smoke check with two typed Urdu sentences (`احمد نے 500 کا ادھار لیا`,
  `احمد کا کتنا باقی ہے؟`): both produced the correct tool call. This is a sanity check, not a benchmark.
- During informal use, at least one real recording failed with "could not understand" (the model made no
  tool call after the retry). The cause has not been analysed yet.

### Gate test (not yet run)

- Urdu transcription quality on real shopkeeper speech: **TODO: fill in after testing**
- Correct tool call / customer / amount / kind on a set of recorded clips: **TODO: fill in after testing (x / 10)**
- Customer name matching on Urdu names: **TODO: fill in after testing**
- End-to-end latency on my machine: **TODO: fill in after testing**

## Known limitations

- Urdu accuracy is unmeasured; the gate test above has not been run.
- Needs a ~6.6 GB model download and enough RAM to run it.
- Tested on one Linux machine only.
- No edit/undo, no auth, single user.

Full list: [docs/limitations.md](docs/limitations.md).

## Licenses

My code is MIT-licensed, see [LICENSE](LICENSE). The Gemma 4 model is **not** covered by that license;
it is used under Google's own Gemma terms, which you accept when you download it. faster-whisper, the
Noto Nastaliq Urdu and Space Grotesk fonts (SIL Open Font License), and the Python dependencies carry
their own licenses.
