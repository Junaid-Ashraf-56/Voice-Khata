# Limitations

Honest list of what is not verified or not handled.

- **Urdu accuracy is unmeasured.** No transcription accuracy, name-matching accuracy or latency numbers
  exist yet. Gemma's Urdu transcription may be weak; `TRANSCRIBE_BACKEND=whisper` is the fallback.
- **Gemma audio through Ollama is unverified.** The Gemma transcriber sends audio as `input_audio` to
  Ollama's OpenAI-compatible `/v1/chat/completions`. Whether your Ollama version and the Gemma 4 E4B
  build accept that has to be confirmed on real hardware. The model tag (`gemma4:e4b`) is the
  configured default and must match `ollama list`.
- **Model size.** Roughly 6 GB of disk and memory for the model (approximate; check `ollama list`).
- **Tested on one machine.** Linux only so far. macOS and Windows are untested.
- **Roman Urdu / code-mixed speech** may transcribe or extract poorly; the prompt asks for Urdu script.
- **Name matching is simple.** Exact (case/space-insensitive) matches are reused; spelling variants
  such as Ahmed/Ahmad become a new customer with a "similar" hint. The user must discard and re-record
  if it is the same person. The same person in two scripts (Urdu vs Latin) is two customers.
- **Amounts** are whole rupees. Spoken amounts like "dhai sau" or "aadha lakh" depend on the model
  converting them to digits; an error here is only caught by the user reading the confirmation.
- **No edit/undo.** There is no way to correct or delete an entry after confirming.
- **Pending proposals live in memory.** They vanish on server restart and are not shared across workers.
- **Single user, no auth, no backups.** The ledger is one local SQLite file.
- **Browser support.** Needs `MediaRecorder` with webm/opus (Chrome, Edge, Firefox). Safari is untested.
  Microphone access requires `localhost` or HTTPS.
