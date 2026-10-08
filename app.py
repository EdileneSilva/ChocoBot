import asyncio
import os, time, uuid
from contextlib import asynccontextmanager
from typing import Literal

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from chatbot import handle_chat  # importe llm.py, qui charge le .env : à garder avant sentry_sdk.init
from observability import request_id, log_event
import db
import llm

SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:  # sans DSN (ex. sur la machine de la binôme), Sentry reste désactivé
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv("SENTRY_ENV", "dev"),
        send_default_pii=False,          # pas d'IP, de cookies ni d'en-têtes personnels
        max_request_body_size="never",   # ne jamais envoyer le corps des requêtes (messages, allergies)
        include_local_variables=False,   # ne pas envoyer les variables (prompt, historique)
        traces_sample_rate=0,            # pas de suivi de performance : sobriété
    )


async def purge_expired_sessions_periodically():
    while True:
        db.purge_expired_sessions()
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    purge_task = asyncio.create_task(purge_expired_sessions_periodically())
    app.state.purge_task = purge_task
    try:
        yield
    finally:
        app.state.purge_task.cancel()
        try:
            await app.state.purge_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="ChocoBot - Maison Delcourt", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


class ChatIn(BaseModel):
    session_id: str
    message: str
    allergies: list[Literal["lait", "fruits à coque", "soja", "gluten", "œufs", "arachides"]] = Field(
        default_factory=list
    )


@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.post("/chat")
def chat(body: ChatIn):
    return handle_chat(body.session_id, body.message, body.allergies)


@app.delete("/session", status_code=204)
def delete_session(session_id: str):
    db.delete_session(session_id)


# Back-office de l'équipe Delcourt : pratique pour voir qui a écrit quoi
@app.get("/admin")
def admin():
    return FileResponse("static/admin.html")


@app.get("/admin/data")
def admin_data():
    data = db.get_all()
    data["llm"] = {"big": llm.BIG_MODEL, "small": llm.SMALL_MODEL}
    return data


@app.get("/health")
def health():
    return {"status": "ok"}


@app.middleware("http")
async def journaliser_requete(request: Request, call_next):
    request_id.set(uuid.uuid4().hex[:8])
    debut = time.perf_counter()
    response = await call_next(request)
    log_event("info", "http_request", method=request.method, path=request.url.path,
              status=response.status_code, duration_ms=round((time.perf_counter() - debut) * 1000))
    response.headers["X-Request-ID"] = request_id.get()
    return response
