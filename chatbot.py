import json, os, re, unicodedata
import db
import llm
import time
from observability import log_event

with open(os.path.join(os.path.dirname(__file__), "data", "catalog.json"), encoding="utf-8") as f:
    CATALOG = json.load(f)

SYSTEM_PROMPT = """Tu es Clémence, assistant virtuel (IA), introduis-toi comme tel, conseillère à la Maison Delcourt, chocolatier artisanal à Lille.
Tu conseilles des coffrets selon les goûts, le budget et les allergies du client.
Réponds toujours en français, de façon chaleureuse et concise : 3 à 4 phrases au maximum, et 2 coffrets au plus.
N'invente ni composition, ni quantité, ni prix : reprends uniquement les informations du catalogue.
Ne prends aucune commande et n'annonce ni e-mail ni livraison : invite le client à commander sur le site.
Ne propose que des coffrets du catalogue fourni, sans inventer de produit ni de prix.
Si le catalogue fourni est vide, explique qu'aucun coffret répertorié ne convient aux allergies indiquées, sans recommander de produit.
"""

ALLERGEN_ALIASES = {

    "fruits a coque": ("fruits a coque", "noisette", "noisettes", "noix", "amande", "amandes",
                       "pistache", "pistaches", "noix de cajou", "noix du bresil", "noix de pecan",
                       "pecan", "pecanes", "macadamia"),
    "lait": ("lait", "lactose"),
    "gluten": ("gluten", "ble", "seigle", "orge", "avoine"),
    "oeuf": ("oeuf", "oeufs"),
    "soja": ("soja",),
    "arachides": ("arachide", "arachides", "cacahuete", "cacahuetes"),
}

with open(os.path.join(os.path.dirname(__file__), "data", "faq.json"), encoding="utf-8") as f:
    FAQ = json.load(f)

_cache = {}        # réponses déjà calculées pour un premier message (en mémoire, jamais enregistrées)
CACHE_MAX = 200
MAX_TOKENS = 300   # filet de sécurité : la consigne demande 3 à 4 phrases (≈ 100 à 150 tokens)
HISTORY_MAX = 6   # 3 derniers échanges (le message en cours compris) envoyés au modèle


def find_faq(message):
    """Réponse fixe pour une question courte sur un sujet connu, sinon None."""
    words = re.findall(r"\w+", normalize_allergen(message))
    if len(words) > 8:   # une phrase longue est une vraie demande : on laisse le modèle répondre
        return None
    return next((entry for entry in FAQ if any(k in words for k in entry["mots_cles"])), None)


MOTS_POLITESSE = ("merci", "ok", "oui", "non", "parfait", "super", "d accord",
                  "bonjour", "bonsoir", "salut", "au revoir")
MOTS_RISQUE = ("allerg", "euro", "prix", "budget", "enfant", "cadeau", "conseil", "recommand")


def choose_model(message):
    """Petit modèle pour la politesse et les confirmations, gros modèle pour tout conseil."""
    texte = " ".join(re.findall(r"\w+", normalize_allergen(message)))
    risque = any(mot.startswith(MOTS_RISQUE) for mot in texte.split())
    if not risque and texte.startswith(MOTS_POLITESSE):
        return llm.SMALL_MODEL
    return llm.BIG_MODEL


def normalize_allergen(value):
    normalized = unicodedata.normalize("NFD", value.casefold().replace("œ", "oe").replace("æ", "ae"))
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def filter_catalog(allergies):
    if not allergies:
        return CATALOG

    if isinstance(allergies, str):
        allergies = [allergies]
    normalized_allergies = normalize_allergen(" ".join(allergies))
    categories = {
        category
        for category, aliases in ALLERGEN_ALIASES.items()
        if any(re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", normalized_allergies) for alias in aliases)
    }

    def contains_allergen(product):
        for allergen in product["allergenes"]:
            normalized = normalize_allergen(allergen)
            category = next(
                (name for name, aliases in ALLERGEN_ALIASES.items() if normalized in aliases),
                normalized,
            )
            if category in categories or re.search(
                rf"(?<!\w){re.escape(normalized)}(?!\w)", normalized_allergies
            ):
                return True
        return False

    return [product for product in CATALOG if not contains_allergen(product)]


def format_catalog(catalog):
    """Une ligne par coffret : nom, prix, contenu, allergènes (moins de tokens que le JSON complet)."""
    return "\n".join(
        f"- {p['nom']} : {p['prix']} € ; {', '.join(p['contenu'])} ; allergènes : {', '.join(p['allergenes']) or 'aucun'}"
        for p in catalog
    )


def handle_chat(session_id, message, allergies=None):
    db.save_message(session_id, "user", message)
    log_event("info", "chat_message", session=session_id[:8], message_length=len(message))

    faq = find_faq(message)
    if faq:
        log_event("info", "faq_hit", faq=faq["id"])
        db.save_message(session_id, "assistant", faq["reponse"])
        return {"reply": faq["reponse"]}

    allergies = allergies or []
    catalog = filter_catalog(allergies)
    system = SYSTEM_PROMPT + "\n\nCatalogue des coffrets compatibles avec les allergies indiquées :\n" + format_catalog(catalog)
    history = db.get_history(session_id)
    cache_key = None
    
    if len(history) == 1:   # premier message de la conversation
        cache_key = (" ".join(re.findall(r"\w+", normalize_allergen(message))), tuple(sorted(allergies)))
        if cache_key in _cache:
            log_event("info", "cache_hit")
            reply = _cache[cache_key]
            db.save_message(session_id, "assistant", reply)
            return {"reply": reply}
    messages = [{"role": "system", "content": system}] + history[-HISTORY_MAX:]

    model = choose_model(message)
    debut = time.perf_counter()
    try:
        reply, usage = llm.chat(model, messages, max_tokens=MAX_TOKENS)
        log_event("info", "llm_call", model=usage["model"], prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                latency_ms=round((time.perf_counter() - debut) * 1000), status="ok")
        if cache_key:
            if len(_cache) >= CACHE_MAX:
                _cache.pop(next(iter(_cache)))   # retire la plus ancienne entrée
            _cache[cache_key] = reply
    except Exception as e:
        log_event("error", "llm_call_failed", exc_info=True, model=model,
                error=type(e).__name__, detail=str(e),
                latency_ms=round((time.perf_counter() - debut) * 1000))
        reply = "Désolé, une erreur est survenue. Réessayez plus tard."
    db.save_message(session_id, "assistant", reply)
    return {"reply": reply}
