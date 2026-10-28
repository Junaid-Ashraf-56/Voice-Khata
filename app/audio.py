"""Browser audio (webm/opus) -> 16 kHz mono WAV, using ffmpeg."""
import os
import subprocess
import tempfile


class AudioError(Exception):
    pass


def to_wav_16k_mono(data: bytes, ffmpeg_bin: str = "ffmpeg") -> bytes:
    if not data:
        raise AudioError("Empty audio upload.")
    # Temp files, not pipes: ffmpeg cannot seek a pipe to write the WAV header sizes.
    with tempfile.TemporaryDirectory(prefix="voicekhata-") as tmp:
        src = os.path.join(tmp, "in.webm")
        dst = os.path.join(tmp, "out.wav")
        with open(src, "wb") as f:
            f.write(data)
        cmd = [ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
               "-i", src, "-vn", "-ar", "16000", "-ac", "1", "-f", "wav", dst]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=60)
        except FileNotFoundError:
            raise AudioError(f"ffmpeg not found ('{ffmpeg_bin}'). Install ffmpeg and retry.")
        except subprocess.TimeoutExpired:
            raise AudioError("ffmpeg timed out converting the audio.")
        if proc.returncode != 0:
            msg = proc.stderr.decode("utf-8", "replace").strip()[-300:]
            raise AudioError(f"Could not decode the recording: {msg}")
        with open(dst, "rb") as f:
            return f.read()
