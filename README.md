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
- Local-only: Gemma via Ollama; optional faster-whisper for stage 1.

## Setup

Requirements: Python 3.10+, [ffmpeg](https://ffmpeg.org/), [Ollama](https://ollama.com/) and a browser with microphone access.

```bash
git clone <this repo> voice-khata && cd voice-khata
cp .env.example .env            # optional; defaults work
ollama pull gemma4:e4b          # ~6 GB; confirm the exact tag with `ollama list` / the Ollama library
make run                        # creates .venv, installs deps, serves http://127.0.0.1:8000
```

Open <http://localhost:8000> (microphone needs `localhost` or HTTPS), press **Record**, speak, press **Stop**.

If your Ollama tag differs, set `MODEL_NAME` in `.env`.

### Tests (offline, model mocked, no ffmpeg or Ollama needed)

```bash
make test
```

### If Gemma's Urdu transcription is weak

Stage 1 can use faster-whisper instead. Uncomment `faster-whisper` in `requirements.txt`, reinstall
(`make setup`), and set `TRANSCRIBE_BACKEND=whisper` and `WHISPER_MODEL=<an Urdu-capable model>` in `.env`.
Stage 2 still uses Gemma.

## How AI is used

**Inside the product** (open-source, run locally):
- **Gemma 4 E4B via Ollama**, stage 1: turns the recorded audio into an Urdu-script transcript.
  The prompt asks for Urdu script and forbids translation.
- **Gemma 4 E4B via Ollama**, stage 2: reads the transcript plus the list of existing customers and
  makes a function call (`add_entry` or `get_balance`). It does not compute balances; SQLite does.
- **faster-whisper** (optional): drop-in replacement for stage 1.
- The model's output is untrusted: it is validated with Pydantic, and a human confirms before saving.

**To build it:** AI coding tools (Claude Code) helped write and review the code, tests and docs in this
repository. I reviewed and ran the result.

See [docs/architecture.md](docs/architecture.md) for the design.

## Test results

Not measured yet. Fill in after testing with real Urdu audio.

- Gate test: Urdu transcription quality on real shopkeeper speech: **TODO: fill in after testing**
- Gate test: customer name matching on Urdu names: **TODO: fill in after testing**
- Gate test: end-to-end latency on my machine: **TODO: fill in after testing**

## Known limitations

- Urdu accuracy is unverified.
- Needs a ~6 GB model download and enough RAM to run it.
- Tested on one machine only.
- No edit/undo, no auth, single user.

Full list: [docs/limitations.md](docs/limitations.md).

## Licenses

My code is MIT-licensed, see [LICENSE](LICENSE). The Gemma 4 model is **not** covered by that license;
it is used under Google's own Gemma terms, which you accept when you download it. faster-whisper and the
Python dependencies carry their own licenses.
