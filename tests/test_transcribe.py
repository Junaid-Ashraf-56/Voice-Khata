import shutil

import pytest

from app.audio import AudioError, to_wav_16k_mono
from app.config import Settings
from app.transcribe import TRANSCRIBE_PROMPT, GemmaTranscriber, WhisperTranscriber, get_transcriber


def test_prompt_requests_urdu_script_and_forbids_translation():
    p = TRANSCRIBE_PROMPT.lower()
    assert "urdu script" in p
    assert "do not translate" in p
    assert "roman" in p  # explicitly not Roman Urdu


def test_backend_selection():
    assert isinstance(get_transcriber(Settings(transcribe_backend="gemma")), GemmaTranscriber)
    assert isinstance(get_transcriber(Settings(transcribe_backend="whisper")), WhisperTranscriber)
    with pytest.raises(ValueError):
        get_transcriber(Settings(transcribe_backend="nope"))


def test_empty_audio_rejected():
    with pytest.raises(AudioError):
        to_wav_16k_mono(b"")


def test_missing_ffmpeg_gives_clear_error():
    with pytest.raises(AudioError, match="ffmpeg not found"):
        to_wav_16k_mono(b"abc", ffmpeg_bin="definitely-not-ffmpeg")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_garbage_audio_gives_clear_error():
    with pytest.raises(AudioError, match="Could not decode"):
        to_wav_16k_mono(b"this is not audio")
