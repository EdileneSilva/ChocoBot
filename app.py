from typing import Literal
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from chatbot import handle_chat
import time, uuid
from fastapi import Request
from observability import request_id, log_event
import db
import llm

app = FastAPI(title="ChocoBot - Maison Delcourt")
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
