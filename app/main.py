"""FastAPI app. Nothing is written to the ledger except through /api/confirm."""
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from . import audio, extract as extract_mod, transcribe as transcribe_mod
from .config import Settings
from .ledger import Ledger, resolve_name
from .schemas import (BalanceAnswer, ConfirmRequest, ConfirmResponse, ProcessResponse, Proposal)

PROPOSAL_TTL_SECONDS = 600
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def create_app(settings: Optional[Settings] = None,
               transcriber: Optional[transcribe_mod.Transcriber] = None,
               chat: Optional[extract_mod.ChatFn] = None,
               to_wav: Optional[Callable[[bytes], bytes]] = None) -> FastAPI:
    """Dependencies can be injected so tests run without ffmpeg or a model."""
    settings = settings or Settings.from_env()
    store = Ledger(settings.db_path)
    transcriber = transcriber or transcribe_mod.get_transcriber(settings)
    chat = chat or extract_mod.ollama_chat(settings)
    to_wav = to_wav or (lambda b: audio.to_wav_16k_mono(b, settings.ffmpeg_bin))
    pending: dict[str, tuple[float, Proposal]] = {}

    def purge_expired() -> None:
        cutoff = time.monotonic() - PROPOSAL_TTL_SECONDS
        for pid in [k for k, (t, _) in pending.items() if t < cutoff]:
            del pending[pid]

    app = FastAPI(title="Voice Khata")

    @app.get("/api/health")
    def health():
        return {"ok": True, "model": settings.model_name,
                "transcribe_backend": settings.transcribe_backend}

    @app.get("/api/customers")
    def customers():
        return [{"name": n, "balance": b} for n, b in store.all_balances()]

    @app.post("/api/process", response_model=ProcessResponse)
    async def process(file: UploadFile = File(...)):
        """Audio in -> transcript -> proposed action. Never writes an entry."""
        data = await file.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Recording is too large.")
        try:
            wav = to_wav(data)
            transcript = transcriber.transcribe(wav)
        except audio.AudioError as e:
            raise HTTPException(400, str(e))
        except transcribe_mod.TranscribeError as e:
            raise HTTPException(422, str(e))
        names = store.customer_names()
        try:
            result = extract_mod.extract(transcript, names, chat=chat)
        except extract_mod.ExtractionError as e:
            # Include what was heard so the user can tell a mishearing from a misparse.
            raise HTTPException(422, {"message": str(e), "transcript": transcript})

        name, is_new, similar = resolve_name(result.customer_name, names)

        if result.action == "get_balance":
            return ProcessResponse(
                transcript=transcript, action="get_balance",
                balance=BalanceAnswer(customer_name=name, found=not is_new,
                                      balance=0 if is_new else store.balance(name),
                                      similar_names=similar))

        purge_expired()
        proposal = Proposal(id=uuid.uuid4().hex, transcript=transcript, customer_name=name,
                            is_new_customer=is_new, similar_names=similar,
                            amount=result.amount, kind=result.kind, note=result.note)
        pending[proposal.id] = (time.monotonic(), proposal)
        return ProcessResponse(transcript=transcript, action="add_entry", proposal=proposal)

    @app.post("/api/confirm", response_model=ConfirmResponse)
    def confirm(req: ConfirmRequest):
        """The only route that writes. The entry comes from the server-held proposal,
        so a client cannot change the amount or name at this step."""
        purge_expired()
        item = pending.pop(req.proposal_id, None)
        if item is None:
            raise HTTPException(404, "No such pending entry (already confirmed, or expired).")
        p = item[1]
        entry_id = store.add_entry(p.customer_name, p.amount, p.kind, p.note)
        return ConfirmResponse(entry_id=entry_id, customer_name=p.customer_name,
                               balance=store.balance(p.customer_name))

    @app.middleware("http")
    async def revalidate_static(request, call_next):
        # Make browsers re-check web/ files so UI updates show up without a hard refresh.
        response = await call_next(request)
        if not request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    if WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


