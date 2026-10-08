import os, random, time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Par défaut : Ollama installé sur votre machine (aucun réglage nécessaire)
BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("LLM_API_KEY", "ollama")
BIG_MODEL = os.getenv("LLM_MODEL_BIG", "llama3.2:3b")
SMALL_MODEL = os.getenv("LLM_MODEL_SMALL", "llama3.2:1b")

from openai import OpenAI

# Un seul client pour toute l'application ; les nouvelles tentatives sont gérées dans chatbot.py
_client = OpenAI(base_url=BASE_URL, api_key=API_KEY, timeout=30, max_retries=0)


def check_models(timeout=3):
    """Vérifie que le serveur de modèles répond et que les deux modèles sont installés ; lève une exception sinon."""
    disponibles = {m.id for m in _client.with_options(timeout=timeout).models.list()}
    manquants = [m for m in (BIG_MODEL, SMALL_MODEL) if m not in disponibles]
    if manquants:
        raise RuntimeError(f"modèle(s) absent(s) : {', '.join(manquants)}")


def chat(model, messages, max_tokens=1500):
    """Retourne (texte, usage). Peut lever une exception (Ollama arrêté, modèle absent, panne simulée)."""
    # Simulation d'incidents (optionnelle, voir .env.example)
    time.sleep(float(os.getenv("EXTRA_LATENCY", "0")))
    if random.random() < float(os.getenv("FAIL_RATE", "0")):
        raise RuntimeError("Panne simulée : 503 service unavailable")

    r = _client.chat.completions.create(model=model, messages=messages, max_tokens=max_tokens, temperature=0.3)
    u = r.usage
    return r.choices[0].message.content, {"model": model,
                                          "prompt_tokens": getattr(u, "prompt_tokens", 0) if u else 0,
                                          "completion_tokens": getattr(u, "completion_tokens", 0) if u else 0}
