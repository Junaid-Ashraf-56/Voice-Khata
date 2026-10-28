"""Stage 1: 16 kHz mono WAV -> Urdu transcript.

Backends share one interface: `transcribe(wav_bytes) -> str`.
"""
import base64
from typing import Protocol

import httpx

from .config import Settings

TRANSCRIBE_PROMPT = (
    "Transcribe this audio exactly as spoken. "
    "The speaker is a shopkeeper speaking Urdu (possibly mixed with a few English words). "
    "Write the transcript in Urdu script (Nastaliq/Arabic script), not Roman Urdu and not Hindi/Devanagari. "
    "Do NOT translate into English or any other language. "
    "Write numbers as digits (for example 500). "
    "Output only the transcript text, with no explanation, quotes or labels."
)


class TranscribeError(Exception):
    pass


class Transcriber(Protocol):
    def transcribe(self, wav: bytes) -> str: ...


class GemmaTranscriber:
    """Sends the WAV to the Gemma model through Ollama's OpenAI-compatible endpoint.

    NOTE: whether the installed Ollama version accepts `input_audio` for this model
    has not been verified on real hardware. See docs/limitations.md.
    """

    def __init__(self, settings: Settings):
        self.s = settings

    def transcribe(self, wav: bytes) -> str:
        payload = {
            "model": self.s.model_name,
            "temperature": 0,
            "stream": False,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": TRANSCRIBE_PROMPT},
                    {"type": "input_audio",
                     "input_audio": {"data": base64.b64encode(wav).decode(), "format": "wav"}},
                ],
            }],
        }
        try:
            r = httpx.post(f"{self.s.ollama_url}/v1/chat/completions", json=payload,
                           timeout=self.s.model_timeout)
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
        except httpx.ConnectError:
            raise TranscribeError(f"Cannot reach Ollama at {self.s.ollama_url}. Is `ollama serve` running?")
        except httpx.HTTPStatusError as e:
            raise TranscribeError(f"Ollama rejected the audio request ({e.response.status_code}): "
                                  f"{e.response.text[:200]}")
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            raise TranscribeError(f"Unexpected response from Ollama: {e}")
        text = (text or "").strip()
        if not text:
            raise TranscribeError("The model returned an empty transcript.")
        return text


class WhisperTranscriber:
    """Alternative stage 1 using faster-whisper (optional dependency)."""

    def __init__(self, settings: Settings):
        self.s = settings
        self._model = None

    def transcribe(self, wav: bytes) -> str:
        import io
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise TranscribeError("faster-whisper is not installed. "
                                  "Uncomment it in requirements.txt and reinstall.")
        if self._model is None:
            self._model = WhisperModel(self.s.whisper_model)
        segments, _ = self._model.transcribe(io.BytesIO(wav), language="ur")
        text = " ".join(seg.text.strip() for seg in segments).strip()
        if not text:
            raise TranscribeError("Whisper returned an empty transcript.")
        return text


def get_transcriber(settings: Settings) -> Transcriber:
    if settings.transcribe_backend == "whisper":
        return WhisperTranscriber(settings)
    if settings.transcribe_backend == "gemma":
        return GemmaTranscriber(settings)
    raise ValueError(f"Unknown TRANSCRIBE_BACKEND: {settings.transcribe_backend!r}")
