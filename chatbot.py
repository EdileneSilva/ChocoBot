import json, os, re, unicodedata
import db
import llm
import time
from pydantic import BaseModel, Field, ValidationError
from observability import log_event

# Chemin modifiable par variable d'environnement (utile pour tester un catalogue corrompu sans toucher au vrai)
CATALOG_PATH = os.getenv("CATALOG_PATH", os.path.join(os.path.dirname(__file__), "data", "catalog.json"))

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


def clear_response_cache():
    _cache.clear()


def purge_expired_cache(now=None):
    cutoff = (time.time() if now is None else now) - db.SESSION_RETENTION_SECONDS
    expired = [key for key, (created_at, _) in _cache.items() if created_at <= cutoff]
    for key in expired:
        del _cache[key]


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


FALLBACK_REPLY = ("Désolé, je ne peux pas répondre pour le moment. "
                  "Vous pouvez réessayer dans quelques instants ou consulter nos coffrets sur notre site.")


def call_model(model, messages):
    """Essaie le modèle choisi, puis le petit modèle en secours. Lève la dernière erreur si tout échoue."""
    tentatives = [model, llm.SMALL_MODEL]
    for numero, modele in enumerate(tentatives, 1):
        debut = time.perf_counter()
        try:
            reply, usage = llm.chat(modele, messages, max_tokens=MAX_TOKENS)
            log_event("info", "llm_call", model=usage["model"], attempt=numero,
                      prompt_tokens=usage["prompt_tokens"], completion_tokens=usage["completion_tokens"],
                      latency_ms=round((time.perf_counter() - debut) * 1000), status="ok")
            return reply
        except Exception as e:
            derniere = numero == len(tentatives)
            log_event("error" if derniere else "warning", "llm_call_failed", exc_info=derniere,
                      model=modele, attempt=numero, error=type(e).__name__, detail=str(e),
                      latency_ms=round((time.perf_counter() - debut) * 1000))
            if derniere:
                raise


def normalize_allergen(value):
    normalized = unicodedata.normalize("NFD", value.casefold().replace("œ", "oe").replace("æ", "ae"))
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


class Coffret(BaseModel):
    """Format attendu pour chaque coffret de data/catalog.json."""
    id: str = Field(pattern=r"^C\d{2,}$")
    nom: str = Field(min_length=1)
    prix: float = Field(gt=0)
    contenu: list[str] = Field(min_length=1)
    allergenes: list[str]
    tags: list[str] = []


def valider_catalogue(donnees):
    """Retourne la liste des problèmes du catalogue (liste vide si tout est correct)."""
    if not isinstance(donnees, list) or not donnees:
        return ["le catalogue doit être une liste non vide de coffrets"]
    erreurs, ids = [], set()
    for position, coffret in enumerate(donnees, 1):
        nom = coffret.get("id", f"coffret n°{position}") if isinstance(coffret, dict) else f"coffret n°{position}"
        try:
            Coffret.model_validate(coffret)
        except ValidationError as e:
            erreurs += [f"{nom} : champ « {'.'.join(map(str, err['loc']))} » : {err['msg']}" for err in e.errors()]
            continue
        if coffret["id"] in ids:
            erreurs.append(f"{nom} : identifiant en double")
        ids.add(coffret["id"])
        # Chaque allergène doit être connu
        declares = set()
        for allergene in coffret["allergenes"]:
            normalise = normalize_allergen(allergene)
            categorie = next((cat for cat, alias in ALLERGEN_ALIASES.items() if normalise in alias), None)
            if categorie is None:
                erreurs.append(f"{nom} : allergène inconnu « {allergene} »")
            else:
                declares.add(categorie)
        # Cohérence : un ingrédient du contenu qui correspond à un allergène doit être déclaré
        contenu = normalize_allergen(" ; ".join(coffret["contenu"]))
        for categorie, alias in ALLERGEN_ALIASES.items():
            trouve = next((a for a in alias if re.search(rf"(?<!\w){re.escape(a)}(?!\w)", contenu)), None)
            if trouve and categorie not in declares:
                erreurs.append(f"{nom} ({coffret['nom']}) : le contenu mentionne « {trouve} » "
                               f"mais l'allergène « {categorie} » n'est pas déclaré")
    return erreurs


def charger_catalogue(chemin=CATALOG_PATH):
    """Lit et valide le catalogue. Retourne (coffrets, erreurs) ; s'il y a une erreur, aucun coffret n'est utilisé."""
    try:
        with open(chemin, encoding="utf-8") as f:
            donnees = json.load(f)
    except FileNotFoundError:
        return [], [f"fichier introuvable : {chemin}"]
    except json.JSONDecodeError as e:
        return [], [f"{os.path.basename(chemin)} : JSON invalide ligne {e.lineno}, colonne {e.colno} : {e.msg} "
                    "(l'erreur peut se trouver à la fin de la ligne précédente)"]
    erreurs = valider_catalogue(donnees)
    return ([] if erreurs else donnees), erreurs


CATALOG, CATALOG_ERREURS = charger_catalogue()
CATALOG_INDISPONIBLE = ("Nos conseils personnalisés sont momentanément indisponibles. "
                        "Vous pouvez consulter nos coffrets et leurs allergènes sur notre site.")


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
    purge_expired_cache()
    db.save_message(session_id, "user", message)
    log_event("info", "chat_message", session=session_id[:8], message_length=len(message))

    faq = find_faq(message)
    if faq:
        log_event("info", "faq_hit", faq=faq["id"])
        db.save_message(session_id, "assistant", faq["reponse"])
        return {"reply": faq["reponse"]}

    if CATALOG_ERREURS:
        # Catalogue invalide : ne jamais conseiller à partir de données fausses (allergènes, prix)
        log_event("warning", "catalog_unavailable")
        return {"reply": CATALOG_INDISPONIBLE}   # jamais enregistrée dans l'historique

    allergies = allergies or []
    catalog = filter_catalog(allergies)
    system = SYSTEM_PROMPT + "\n\nCatalogue des coffrets compatibles avec les allergies indiquées :\n" + format_catalog(catalog)
    history = db.get_history(session_id)
    cache_key = None

    if len(history) == 1:   # premier message de la conversation
        cache_key = (" ".join(re.findall(r"\w+", normalize_allergen(message))), tuple(sorted(allergies)))
        if cache_key in _cache:
            log_event("info", "cache_hit")
            reply = _cache[cache_key][1]
            db.save_message(session_id, "assistant", reply)
            return {"reply": reply}
    messages = [{"role": "system", "content": system}] + history[-HISTORY_MAX:]

    model = choose_model(message)
    try:
        reply = call_model(model, messages)
    except Exception:
        return {"reply": FALLBACK_REPLY}   # réponse de secours, jamais enregistrée dans l'historique
    if cache_key:
        if len(_cache) >= CACHE_MAX:
            _cache.pop(next(iter(_cache)))   # retire la plus ancienne entrée
        _cache[cache_key] = (time.time(), reply)
    db.save_message(session_id, "assistant", reply)
    return {"reply": reply}
