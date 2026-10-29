# Limitations

Honest list of what is not verified or not handled.

- **Urdu accuracy is unmeasured.** No transcription accuracy, name-matching accuracy or latency numbers
  exist yet. Gemma's Urdu transcription may be weak; `TRANSCRIBE_BACKEND=whisper` is the fallback.
- **Gemma audio input depends on the Ollama version.** The Gemma transcriber sends audio as `input_audio`
  to Ollama's OpenAI-compatible `/v1/chat/completions`. This works with Ollama 0.40.13 and `gemma4:e4b`
  on the test machine; other versions are untested. The model tag must match `ollama list`.
- **Model size.** `gemma4:e4b` (Q4_K_M) is 6.58 GB on disk and needs comparable memory to run.
- **Fonts load from Google Fonts.** Offline, Urdu text falls back to a system font.
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
