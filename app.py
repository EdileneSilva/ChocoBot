import asyncio
import os, secrets, time, uuid
from contextlib import asynccontextmanager
from typing import Literal

import sentry_sdk
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

from chatbot import CATALOG_ERREURS, clear_response_cache, handle_chat, purge_expired_cache  # importe llm.py avant sentry_sdk.init
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

if CATALOG_ERREURS:
    # Signalé ici, après sentry_sdk.init, pour que l'erreur parte aussi vers Sentry
    log_event("error", "catalog_invalid", erreurs=CATALOG_ERREURS)


async def purge_expired_sessions_periodically():
    while True:
        db.purge_expired_sessions()
        purge_expired_cache()
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
admin_auth = HTTPBasic()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


def require_admin(credentials: HTTPBasicCredentials = Depends(admin_auth)) -> None:
    if not ADMIN_PASSWORD:
        raise HTTPException(status_code=503, detail="Le back-office n'est pas configuré.")

    username_matches = secrets.compare_digest(credentials.username, "admin")
    password_matches = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (username_matches and password_matches):
        raise HTTPException(
            status_code=401,
            detail="Identifiants invalides.",
            headers={"WWW-Authenticate": "Basic"},
        )


class ChatIn(BaseModel):
    session_id: str
    message: str
    privacy_consent: bool
    allergies: list[Literal["lait", "fruits à coque", "soja", "gluten", "œufs", "arachides"]] = Field(
        default_factory=list
    )


@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.get("/confidentialite")
def privacy():
    return FileResponse("static/privacy.html")


@app.post("/chat")
def chat(body: ChatIn):
    if not body.privacy_consent:
        raise HTTPException(status_code=403, detail="L'acceptation de la notice de confidentialité est requise.")
    return handle_chat(body.session_id, body.message, body.allergies)


@app.delete("/session", status_code=204)
def delete_session(session_id: str):
    db.delete_session(session_id)
    clear_response_cache()


# Back-office de l'équipe Delcourt : pratique pour voir qui a écrit quoi
@app.get("/admin")
def admin():
    # This page is only the login shell; conversation data remains protected by /admin/data.
    return FileResponse("static/admin.html")


@app.get("/admin/data", dependencies=[Depends(require_admin)])
def admin_data():
    data = db.get_all()
    data["llm"] = {"big": llm.BIG_MODEL, "small": llm.SMALL_MODEL}
    return data


@app.get("/health")
def health():
    """Vérifie réellement la base, le serveur de modèles et le catalogue ; répond 503 si l'un d'eux pose problème."""
    checks = {}
    try:
        db.conn.execute("SELECT 1").fetchone()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"erreur : {type(e).__name__} ({e})"
    try:
        llm.check_models()
        checks["llm"] = "ok"
    except Exception as e:
        checks["llm"] = f"erreur : {type(e).__name__} ({e})"
    checks["catalogue"] = "ok" if not CATALOG_ERREURS else f"erreur : {len(CATALOG_ERREURS)} problème(s), voir les logs"
    ok = all(etat == "ok" for etat in checks.values())
    if not ok:
        # warning et non error : /health peut être appelé souvent, on évite une alerte Sentry à chaque appel
        log_event("warning", "health_check_failed", **checks)
    return JSONResponse({"status": "ok" if ok else "degraded", "checks": checks}, status_code=200 if ok else 503)


@app.middleware("http")
async def journaliser_requete(request: Request, call_next):
    request_id.set(uuid.uuid4().hex[:8])
    debut = time.perf_counter()
    response = await call_next(request)
    log_event("info", "http_request", method=request.method, path=request.url.path,
              status=response.status_code, duration_ms=round((time.perf_counter() - debut) * 1000))
    response.headers["X-Request-ID"] = request_id.get()
    return response
