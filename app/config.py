"""Settings, read from environment variables (and a local .env if present)."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    ollama_url: str = "http://localhost:11434"
    model_name: str = "gemma4:e4b"
    transcribe_backend: str = "gemma"  # "gemma" | "whisper"
    whisper_model: str = "small"
    db_path: str = "data/khata.db"
    ffmpeg_bin: str = "ffmpeg"
    model_timeout: float = 120.0

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        d = cls()
        return cls(
            ollama_url=os.getenv("OLLAMA_URL", d.ollama_url).rstrip("/"),
            model_name=os.getenv("MODEL_NAME", d.model_name),
            transcribe_backend=os.getenv("TRANSCRIBE_BACKEND", d.transcribe_backend).lower(),
            whisper_model=os.getenv("WHISPER_MODEL", d.whisper_model),
            db_path=os.getenv("DB_PATH", d.db_path),
            ffmpeg_bin=os.getenv("FFMPEG_BIN", d.ffmpeg_bin),
            model_timeout=float(os.getenv("MODEL_TIMEOUT", d.model_timeout)),
        )
