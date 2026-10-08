import json, os, re, unicodedata
import db
import llm

with open(os.path.join(os.path.dirname(__file__), "data", "catalog.json"), encoding="utf-8") as f:
    CATALOG = json.load(f)

SYSTEM_PROMPT = """Tu es Clémence, assistant virtuel (IA), introduis-toi comme tel, conseillère à la Maison Delcourt, chocolatier artisanal à Lille.
Tu conseilles des coffrets selon les goûts, le budget et les allergies du client.
Réponds toujours en français, de façon chaleureuse, détaillée et complète, en présentant plusieurs options.
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


def handle_chat(session_id, message, allergies=None):
    db.save_message(session_id, "user", message)
    print(f"[chat] : {message}")

    allergies = allergies or []
    catalog = filter_catalog(allergies)
    system = SYSTEM_PROMPT + "\n\nCatalogue des coffrets compatibles avec les allergies indiquées : " + json.dumps(
        catalog, ensure_ascii=False
    )
    messages = [{"role": "system", "content": system}] + db.get_history(session_id)

    try:
        reply, usage = llm.chat(llm.BIG_MODEL, messages, max_tokens=1500)
    except Exception:
        reply = "Désolé, une erreur est survenue. Réessayez plus tard."

    db.save_message(session_id, "assistant", reply)
    return {"reply": reply}
