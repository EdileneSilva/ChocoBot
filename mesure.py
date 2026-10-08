"""Mesure avant/après de ChocoBot, sans passer par le serveur.
Usage : python mesure.py avant     (puis, après les corrections : python mesure.py apres)
Résultat : mesures_avant.json / mesures_apres.json"""
import json, statistics, sys, time
import llm

LABEL = sys.argv[1] if len(sys.argv) > 1 else "avant"
N_CONV = 3
SCENARIO = [  # identique à load_test.py
    "Quels sont vos horaires ?",
    "Je cherche un coffret pour 30 euros, mon fils est allergique aux noisettes.",
    "Et pour les enfants, vous avez quoi ?",
    "Quels sont vos horaires ?",
    "Merci, je prends le coffret sans noix !",
]
# Coffrets du catalogue contenant des fruits à coque (noisettes)
DANGEREUX = ["Beffroi", "Vegan Flandres", "Grand Coffret", "Mendiants"]

appels = []
_chat_original = llm.chat

def espion(*args, **kwargs):
    modele = args[0] if args else kwargs.get("model")
    t0 = time.perf_counter()
    try:
        texte, usage = _chat_original(*args, **kwargs)
    except Exception as e:
        appels.append({"model": modele, "ok": False, "latence_s": time.perf_counter() - t0, "erreur": str(e)})
        raise
    appels.append({**usage, "model": modele, "ok": True, "latence_s": time.perf_counter() - t0})
    return texte, usage

llm.chat = espion
import chatbot  # importé après le remplacement

try:
    from codecarbon import EmissionsTracker
    tracker = EmissionsTracker(project_name=f"chocobot-{LABEL}", save_to_file=False, log_level="error")
except ImportError:
    tracker = None
    print("codecarbon absent : pas de mesure d'énergie (pip install codecarbon)")

# Échauffement : charger les modèles en mémoire pour ne pas fausser la première latence
for m in {llm.BIG_MODEL, llm.SMALL_MODEL}:
    _chat_original(m, [{"role": "user", "content": "Bonjour"}], max_tokens=5)

run = int(time.time())
reponses = []
if tracker:
    tracker.start()
debut = time.perf_counter()
for i in range(N_CONV):
    sid = f"mesure-{LABEL}-{run}-{i}"
    for msg in SCENARIO:
        n = len(appels)
        t0 = time.perf_counter()
        rep = chatbot.handle_chat(sid, msg, ["fruits à coque"])["reply"]
        reponses.append({"conversation": i, "question": msg, "reponse": rep,
                         "duree_s": round(time.perf_counter() - t0, 2), "appels_llm": len(appels) - n})
duree_totale = time.perf_counter() - debut
co2_kg = tracker.stop() if tracker else None
energie_kwh = getattr(getattr(tracker, "final_emissions_data", None), "energy_consumed", None)

ok = [a for a in appels if a["ok"]]
def total(cle):
    return sum(a.get(cle) or 0 for a in ok)
durees = sorted(r["duree_s"] for r in reponses)
allergie = [r for r in reponses if "allergique" in r["question"]]
dangereuses = sum(any(nom.lower() in r["reponse"].lower() for nom in DANGEREUX) for r in allergie)

resultat = {
    "label": LABEL,
    "messages": len(reponses),
    "appels_llm": len(appels),
    "appels_par_modele": {m: sum(a["model"] == m for a in appels) for m in {a["model"] for a in appels}},
    "erreurs_llm": len(appels) - len(ok),
    "tokens_entree_total": total("prompt_tokens"),
    "tokens_sortie_total": total("completion_tokens"),
    "tokens_entree_par_message": round(total("prompt_tokens") / len(reponses), 1),
    "tokens_sortie_par_message": round(total("completion_tokens") / len(reponses), 1),
    "latence_moyenne_s": round(statistics.mean(durees), 2),
    "latence_p95_s": durees[int(0.95 * (len(durees) - 1))],
    "latence_max_s": durees[-1],
    "longueur_moyenne_reponse": round(statistics.mean(len(r["reponse"]) for r in reponses)),
    "recommandations_dangereuses": f"{dangereuses}/{len(allergie)} (à vérifier à la main)",
    "duree_totale_s": round(duree_totale, 1),
    "energie_kwh": energie_kwh,
    "co2_kg": co2_kg,
    "detail_reponses": reponses,
}
with open(f"mesures_{LABEL}.json", "w", encoding="utf-8") as f:
    json.dump(resultat, f, ensure_ascii=False, indent=2)
print(json.dumps({k: v for k, v in resultat.items() if k != "detail_reponses"}, ensure_ascii=False, indent=2))