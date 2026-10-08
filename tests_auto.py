"""Rejoue automatiquement les tests de la phase 1 (sobriété et fiabilité) sur la version actuelle du code.

Usage (dans le venv, Ollama démarré) :
    python tests_auto.py --label apres                 # tous les tests (≈ 10 min)
    python tests_auto.py --label v2 --rapide           # seulement les tests de pannes et de catalogue (≈ 1 min)
    python tests_auto.py --label v2 --reference mesures/apres/resultats.json

Résultats : mesures/<label>/resultats.json, mesures/<label>/rapport.md et les logs des serveurs de test.

Le code est copié dans un dossier temporaire avant les tests : la base chocobot.db et le catalogue du projet
ne sont jamais modifiés. Les serveurs de test tournent sur le port 8765, avec Sentry désactivé (les pannes
provoquées ne doivent pas déclencher de vraies alertes).
"""
import argparse, json, os, shutil, sqlite3, statistics, subprocess, sys, tempfile, time, urllib.error, urllib.request
from datetime import datetime

PROJET = os.path.dirname(os.path.abspath(__file__))
PORT = 8765
URL = f"http://127.0.0.1:{PORT}"
PYTHON = sys.executable
TEXTES_CLIENTS = ["allergique aux noisettes", "je prends le coffret sans noix"]   # ne doivent jamais apparaître dans les logs
REPONSE_CATALOGUE_KO = "momentanément indisponibles"


# ---------- outils ----------

def copier_projet(destination):
    """Copie le code (sans venv, git, base, mesures) dans un dossier de test isolé."""
    ignorer = shutil.ignore_patterns(".venv", ".git", "__pycache__", "mesures", "chocobot.db", "mesures_*.json", "*.log")
    shutil.copytree(PROJET, destination, ignore=ignorer, dirs_exist_ok=True)


def env_test(**extra):
    env = dict(os.environ, SENTRY_DSN="", CHOCOBOT_URL=URL, PYTHONUNBUFFERED="1")
    env.update({k: str(v) for k, v in extra.items()})
    return env


def requete(methode, chemin, corps=None, timeout=180):
    """Renvoie (code HTTP, contenu JSON ou texte, durée en s)."""
    donnees = json.dumps(corps).encode() if corps is not None else None
    req = urllib.request.Request(URL + chemin, donnees, {"Content-Type": "application/json"}, method=methode)
    debut = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            code, texte = r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        code, texte = e.code, e.read().decode()
    duree = round(time.perf_counter() - debut, 3)
    try:
        return code, json.loads(texte), duree
    except ValueError:
        return code, texte, duree


def chat(message, session, allergies=("fruits à coque",)):
    return requete("POST", "/chat", {"session_id": session, "message": message,
                                     "allergies": list(allergies), "privacy_consent": True})


class Serveur:
    """Lance uvicorn dans le dossier de test et l'arrête à la sortie du bloc `with`."""

    def __init__(self, dossier, journal, **env_extra):
        self.dossier, self.journal, self.env = dossier, journal, env_test(**env_extra)
        self.demarre = False

    def __enter__(self):
        base = os.path.join(self.dossier, "chocobot.db")
        if os.path.exists(base):
            os.remove(base)                     # base vide à chaque test
        self.fichier = open(self.journal, "w", encoding="utf-8")
        self.proc = subprocess.Popen([PYTHON, "-m", "uvicorn", "app:app", "--port", str(PORT)], cwd=self.dossier,
                                     env=self.env, stdout=self.fichier, stderr=subprocess.STDOUT)
        for _ in range(60):
            if self.proc.poll() is not None:
                break                           # le serveur s'est arrêté tout seul (démarrage impossible)
            try:
                urllib.request.urlopen(URL + "/", timeout=1)
                self.demarre = True
                break
            except Exception:
                time.sleep(0.5)
        return self

    def __exit__(self, *exc):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.fichier.close()

    def log(self):
        with open(self.journal, encoding="utf-8") as f:
            return f.read()

    def base(self, sql):
        con = sqlite3.connect(os.path.join(self.dossier, "chocobot.db"))
        try:
            return con.execute(sql).fetchall()
        finally:
            con.close()


def evenements(texte_log, nom=None, niveau=None):
    """Lignes JSON du log (B1), filtrées par nom d'événement et niveau."""
    lignes = []
    for ligne in texte_log.splitlines():
        if ligne.startswith("{"):
            try:
                ev = json.loads(ligne)
            except ValueError:
                continue
            if (nom is None or ev.get("event") == nom) and (niveau is None or ev.get("level") == niveau):
                lignes.append(ev)
    return lignes


def etape(titre):
    print(f"\n=== {titre} ({datetime.now():%H:%M:%S})", flush=True)


# ---------- tests ----------

def test_consommation(dossier, label, runs):
    """Test 1 : mesure.py (15 messages, tokens, latence, énergie) lancé plusieurs fois."""
    executions = []
    for i in range(1, runs + 1):
        etape(f"Test 1 — consommation, exécution {i}/{runs}")
        for f in ("chocobot.db", f"mesures_{label}.json"):
            if os.path.exists(os.path.join(dossier, f)):
                os.remove(os.path.join(dossier, f))
        p = subprocess.run([PYTHON, "mesure.py", label], cwd=dossier, env=env_test(), capture_output=True, text=True)
        chemin = os.path.join(dossier, f"mesures_{label}.json")
        if p.returncode != 0 or not os.path.exists(chemin):
            print(p.stdout[-2000:], p.stderr[-2000:])
            raise RuntimeError("mesure.py a échoué (Ollama est-il démarré ?)")
        with open(chemin, encoding="utf-8") as f:
            executions.append(json.load(f))
    def moy(cle):   # moyenne sans arrondi : l'énergie et le CO₂ sont de très petites valeurs
        valeurs = [e[cle] for e in executions if e.get(cle) is not None]
        return statistics.mean(valeurs) if valeurs else None
    n_msg = executions[0]["messages"]
    gros = statistics.mean(e["appels_par_modele"].get("llama3.2:3b", 0) for e in executions)
    appels = statistics.mean(e["appels_llm"] for e in executions)
    energie = moy("energie_kwh")
    co2 = moy("co2_kg")
    return {
        "executions": runs,
        "messages_par_execution": n_msg,
        "appels_llm": round(appels, 1),
        "appels_gros_modele": round(gros, 1),
        "part_gros_modele_pct": round(100 * gros / n_msg, 1),
        "tokens_entree_par_message": round(moy("tokens_entree_par_message"), 1),
        "tokens_sortie_par_message": round(moy("tokens_sortie_par_message"), 1),
        "tokens_total": round(statistics.mean(e["tokens_entree_total"] + e["tokens_sortie_total"] for e in executions)),
        "latence_moyenne_s": round(moy("latence_moyenne_s"), 2),
        "latence_p95_s": round(moy("latence_p95_s"), 2),
        "longueur_moyenne_reponse": round(moy("longueur_moyenne_reponse")),
        "energie_wh_par_message": round(energie * 1000 / n_msg, 4) if energie is not None else None,
        "co2_mg": round(co2 * 1e6, 1) if co2 is not None else None,
        "reco_dangereuses_allergie_auto": [e["recommandations_dangereuses"].split()[0] for e in executions],
        "reco_dangereuses_enfants_auto": [e.get("recommandations_dangereuses_enfants", "?").split()[0] for e in executions],
        "reponses_a_verifier": [
            {"execution": i + 1, "question": r["question"], "reponse": r["reponse"]}
            for i, e in enumerate(executions) for r in e["detail_reponses"]
            if "allergique" in r["question"] or "enfants" in r["question"]
        ],
    }


def test_bout_en_bout(dossier, logs):
    etape("Test 2 — de bout en bout (load_test.py 2)")
    with Serveur(dossier, os.path.join(logs, "test2_serveur.log")) as s:
        debut = time.perf_counter()
        p = subprocess.run([PYTHON, "load_test.py", "2"], cwd=dossier, env=env_test(), capture_output=True, text=True)
        duree = round(time.perf_counter() - debut, 1)
        reponses = s.base("SELECT COUNT(*) FROM messages WHERE role='assistant'")[0][0]
    return {"duree_s": duree, "reussi": p.returncode == 0, "reponses_enregistrees": reponses, "messages_envoyes": 10}


def test_charge(dossier, logs, ecart_s, nom):
    etape(f"Test 3{nom} — 5 clients en parallèle (écart {ecart_s} s)")
    with Serveur(dossier, os.path.join(logs, f"test3{nom}_serveur.log")) as s:
        debut = time.perf_counter()
        clients = []
        for _ in range(5):
            clients.append((time.perf_counter(), subprocess.Popen(
                [PYTHON, "load_test.py", "1"], cwd=dossier, env=env_test(),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)))
            if ecart_s:
                time.sleep(ecart_s)
        durees, reussis = [], 0
        for depart, p in clients:
            p.communicate()
            durees.append(time.perf_counter() - depart)
            reussis += p.returncode == 0
        duree = round(time.perf_counter() - debut, 1)
        log = s.log()
        sessions = s.base("SELECT COUNT(DISTINCT session_id) FROM messages")[0][0]
    erreurs_500 = log.count('" 500')
    return {
        "clients_termines": reussis, "clients": 5,
        "erreurs_500": erreurs_500,
        "erreurs_sqlite": log.count("sqlite3."),
        "duree_totale_s": duree,
        "temps_par_message_client_s": round(statistics.mean(durees) / 5, 1),
        "sessions_distinctes": sessions,
    }


def test_panne_api(dossier, logs):
    etape("Test 4 — panne de l'API du modèle (FAIL_RATE=1)")
    with Serveur(dossier, os.path.join(logs, "test4_serveur.log"), FAIL_RATE=1) as s:
        resultats = [chat(m, "test4") for m in ("Bonjour, un coffret à 30 euros ?", "Un cadeau pour ma mère",
                                                 "Quels sont vos horaires ?")]
        sante = requete("GET", "/health")
        log = s.log()
        enregistrees = s.base("SELECT COUNT(*) FROM messages WHERE session_id='test4' AND role='assistant'")[0][0]
    return {
        "codes_http": [r[0] for r in resultats],
        "reponses": [r[1].get("reply") if isinstance(r[1], dict) else r[1] for r in resultats],
        "duree_max_s": max(r[2] for r in resultats),
        "erreurs_journalisees": len(evenements(log, "llm_call_failed", "ERROR")),
        "tentatives_journalisees_warning": len(evenements(log, "llm_call_failed", "WARNING")),
        "cause_visible_dans_log": "503 service unavailable" in log,
        "reponses_assistant_enregistrees": enregistrees,   # seule la réponse FAQ doit l'être
        "health_code": sante[0], "health": sante[1],
    }


def test_ollama_injoignable(dossier, logs):
    etape("Test 4b — serveur de modèles injoignable")
    with Serveur(dossier, os.path.join(logs, "test4b_serveur.log"), LLM_BASE_URL="http://127.0.0.1:9/v1") as s:
        conseil = chat("Un coffret à 30 euros", "test4b")
        faq = chat("Livraison ?", "test4b")
        sante = requete("GET", "/health")
        log = s.log()
    return {
        "reponse_conseil": conseil[1].get("reply") if isinstance(conseil[1], dict) else conseil[1],
        "duree_conseil_s": conseil[2],
        "faq_fonctionne": isinstance(faq[1], dict) and "livraison" in faq[1].get("reply", "").lower(),
        "erreur_journalisee": len(evenements(log, "llm_call_failed", "ERROR")),
        "health_code": sante[0], "health": sante[1],
    }


def test_catalogue(dossier, logs, nom, corrompre):
    etape(f"Test 5{nom} — catalogue corrompu")
    chemin = os.path.join(dossier, "data", "catalog.json")
    with open(chemin, encoding="utf-8") as f:
        original = f.read()
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(corrompre(original))
    try:
        with Serveur(dossier, os.path.join(logs, f"test5{nom}_serveur.log")) as s:
            res = {"serveur_demarre": s.demarre}
            if s.demarre:
                sante = requete("GET", "/health")
                conseil = chat("Je suis allergique aux fruits à coque, que me conseillez-vous autour de 25 euros ?",
                               f"test5{nom}")
                faq = chat("Livraison ?", f"test5{nom}")
                reponse = conseil[1].get("reply", "") if isinstance(conseil[1], dict) else str(conseil[1])
                res.update({
                    "health_code": sante[0],
                    "conseil_refuse": REPONSE_CATALOGUE_KO in reponse,
                    "beffroi_propose": "beffroi" in reponse.lower(),
                    "faq_fonctionne": isinstance(faq[1], dict) and "livraison" in faq[1].get("reply", "").lower(),
                })
            log = s.log()
        alertes = evenements(log, "catalog_invalid", "ERROR")
        res["erreur_detectee"] = bool(alertes)
        res["message"] = alertes[0]["erreurs"] if alertes else None
        res["lignes_de_log_au_demarrage"] = len([l for l in log.splitlines() if l.strip()])
    finally:
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(original)
    return res


def corrompre_virgule(texte):
    lignes = texte.split("\n")
    lignes[1] = lignes[1].rstrip().rstrip(",")
    return "\n".join(lignes)


def corrompre_allergene(texte):
    cat = json.loads(texte)
    cat[0]["allergenes"] = [a for a in cat[0]["allergenes"] if a != "fruits à coque"]
    return json.dumps(cat, ensure_ascii=False, indent=1)


def test_confidentialite(logs):
    etape("Contrôle — textes des clients dans les logs")
    trouves = {}
    for nom in sorted(os.listdir(logs)):
        with open(os.path.join(logs, nom), encoding="utf-8") as f:
            contenu = f.read().lower()
        for t in TEXTES_CLIENTS:
            if t in contenu:
                trouves.setdefault(nom, []).append(t)
    return {"logs_verifies": len(os.listdir(logs)), "textes_clients_trouves": trouves}


# ---------- rapport ----------

def ligne(nom, ref, cur, unite=""):
    def f(v):
        return "—" if v is None else (f"{v}{unite}" if not isinstance(v, (list, dict)) else str(v))
    gain = ""
    if isinstance(ref, (int, float)) and isinstance(cur, (int, float)) and ref:
        d = (cur - ref) / ref * 100
        gain = f"{d:+.0f} %"
    return f"| {nom} | {f(ref)} | {f(cur)} | {gain} |"


def lisible(v):
    """Valeur affichable dans le rapport : — si absente, oui/non pour les booléens."""
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "oui" if v else "non"
    return v


def rapport(res, ref):
    r, g = res, (lambda *cles: lisible(_get(ref, cles)))
    c = r.get("consommation", {})
    lignes = [f"# Rapport des tests automatiques — {r['label']}", "",
              f"Date : {r['date']} · Code : `{r['commit']}` · Référence : {r.get('reference') or 'aucune'}", "",
              "Généré par `tests_auto.py`. Les recommandations dangereuses comptées automatiquement doivent être "
              "vérifiées à la main (réponses listées en fin de `resultats.json`).", ""]
    if c:
        lignes += ["## Consommation (test 1, moyenne des exécutions)", "",
                   "| Indicateur | Référence | Actuel | Écart |", "|---|---|---|---|",
                   ligne("Appels au modèle (15 messages)", g("consommation", "appels_llm"), c["appels_llm"]),
                   ligne("Part du gros modèle", g("consommation", "part_gros_modele_pct"), c["part_gros_modele_pct"], " %"),
                   ligne("Tokens d'entrée / message", g("consommation", "tokens_entree_par_message"), c["tokens_entree_par_message"]),
                   ligne("Tokens de sortie / message", g("consommation", "tokens_sortie_par_message"), c["tokens_sortie_par_message"]),
                   ligne("Tokens totaux (15 messages)", g("consommation", "tokens_total"), c["tokens_total"]),
                   ligne("Latence moyenne", g("consommation", "latence_moyenne_s"), c["latence_moyenne_s"], " s"),
                   ligne("Latence p95", g("consommation", "latence_p95_s"), c["latence_p95_s"], " s"),
                   ligne("Longueur moyenne des réponses", g("consommation", "longueur_moyenne_reponse"), c["longueur_moyenne_reponse"], " car."),
                   ligne("Énergie / message", g("consommation", "energie_wh_par_message"), c["energie_wh_par_message"], " Wh"),
                   ligne("CO₂e (15 messages)", g("consommation", "co2_mg"), c["co2_mg"], " mg"),
                   ligne("Reco. dangereuses, question allergie (auto)", g("consommation", "reco_dangereuses_allergie_auto"), c["reco_dangereuses_allergie_auto"]),
                   ligne("Reco. dangereuses, question enfants (auto)", g("consommation", "reco_dangereuses_enfants_auto"), c["reco_dangereuses_enfants_auto"]),
                   ""]
    if "bout_en_bout" in r:
        b = r["bout_en_bout"]
        lignes += ["## De bout en bout et charge (tests 2 et 3)", "",
                   "| Indicateur | Référence | Actuel | Écart |", "|---|---|---|---|",
                   ligne("load_test.py 2 : durée", g("bout_en_bout", "duree_s"), b["duree_s"], " s")]
        for cle, titre in (("charge_simultanee", "Pic simultané (3a)"), ("charge_echelonnee", "Pic échelonné (3b)")):
            x = r[cle]
            lignes += [ligne(f"{titre} : clients terminés / 5", g(cle, "clients_termines"), x["clients_termines"]),
                       ligne(f"{titre} : erreurs HTTP 500", g(cle, "erreurs_500"), x["erreurs_500"]),
                       ligne(f"{titre} : durée totale", g(cle, "duree_totale_s"), x["duree_totale_s"], " s"),
                       ligne(f"{titre} : temps par message vu par un client", g(cle, "temps_par_message_client_s"), x["temps_par_message_client_s"], " s")]
        lignes.append("")
    p, o = r["panne_api"], r["ollama_injoignable"]
    lignes += ["## Pannes (tests 4 et 4b)", "",
               "| Indicateur | Référence | Actuel |", "|---|---|---|",
               f"| Panne API : erreur journalisée (ERROR) | {g('panne_api', 'erreurs_journalisees')} | {lisible(p['erreurs_journalisees'])} |",
               f"| Panne API : cause visible dans le log | {g('panne_api', 'cause_visible_dans_log')} | {lisible(p['cause_visible_dans_log'])} |",
               f"| Panne API : réponses d'erreur enregistrées comme réponses | {g('panne_api', 'reponses_erreur_enregistrees')} | {max(p['reponses_assistant_enregistrees'] - 1, 0)} |",
               f"| Panne API : réponse reçue par le client | {g('panne_api', 'reponse_client')} | {p['reponses'][0]} |",
               f"| Serveur de modèles injoignable : `/health` | {g('ollama_injoignable', 'health_code')} | {lisible(o['health_code'])} |",
               f"| Serveur de modèles injoignable : durée de la réponse | — | {o['duree_conseil_s']} s |",
               f"| Serveur de modèles injoignable : FAQ disponible | — | {lisible(o['faq_fonctionne'])} |", ""]
    a, b5 = r["catalogue_json_invalide"], r["catalogue_allergene_retire"]
    lignes += ["## Catalogue corrompu (tests 5a et 5b)", "",
               "| Indicateur | Référence | Actuel |", "|---|---|---|",
               f"| 5a JSON invalide : serveur démarre | {g('catalogue_json_invalide', 'serveur_demarre')} | {lisible(a['serveur_demarre'])} |",
               f"| 5a JSON invalide : erreur détectée et signalée | {g('catalogue_json_invalide', 'erreur_detectee')} | {lisible(a['erreur_detectee'])} |",
               f"| 5a JSON invalide : `/health` | {g('catalogue_json_invalide', 'health_code')} | {lisible(a.get('health_code'))} |",
               f"| 5b allergène retiré : erreur détectée | {g('catalogue_allergene_retire', 'erreur_detectee')} | {lisible(b5['erreur_detectee'])} |",
               f"| 5b allergène retiré : Beffroi proposé à un allergique | {g('catalogue_allergene_retire', 'beffroi_propose')} | {lisible(b5.get('beffroi_propose'))} |",
               f"| 5b allergène retiré : `/health` | {g('catalogue_allergene_retire', 'health_code')} | {lisible(b5.get('health_code'))} |", "",
               f"Messages 5a : {a['message']}", "", f"Messages 5b : {b5['message']}", ""]
    conf = r["confidentialite"]
    lignes += ["## Confidentialité des logs", "",
               f"{conf['logs_verifies']} logs de serveur vérifiés ; textes de clients retrouvés : "
               f"{conf['textes_clients_trouves'] or 'aucun'}.", ""]
    return "\n".join(lignes)


def _get(d, cles):
    for c in cles:
        if not isinstance(d, dict) or c not in d:
            return None
        d = d[c]
    return d


# ---------- programme principal ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", default="apres", help="nom de la série de mesures (dossier mesures/<label>)")
    ap.add_argument("--runs", type=int, default=3, help="nombre d'exécutions de mesure.py (défaut : 3)")
    ap.add_argument("--rapide", action="store_true", help="sauter les tests longs (consommation, bout en bout, charge)")
    ap.add_argument("--reference", default=os.path.join(PROJET, "mesures", "avant", "resultats.json"),
                    help="résultats de référence à comparer (défaut : mesures/avant/resultats.json)")
    args = ap.parse_args()

    sortie = os.path.join(PROJET, "mesures", args.label)
    logs = os.path.join(sortie, "logs")
    os.makedirs(logs, exist_ok=True)
    try:
        commit = subprocess.run(["git", "describe", "--always", "--dirty"], cwd=PROJET,
                                capture_output=True, text=True).stdout.strip() or "?"
    except FileNotFoundError:
        commit = "?"
    res = {"label": args.label, "date": f"{datetime.now():%Y-%m-%d %H:%M}", "commit": commit,
           "reference": os.path.relpath(args.reference, PROJET) if os.path.exists(args.reference) else None}

    with tempfile.TemporaryDirectory(prefix="chocobot-tests-") as dossier:
        copier_projet(dossier)
        if not args.rapide:
            res["consommation"] = test_consommation(dossier, args.label, args.runs)
            res["bout_en_bout"] = test_bout_en_bout(dossier, logs)
            res["charge_simultanee"] = test_charge(dossier, logs, 0, "a")
            res["charge_echelonnee"] = test_charge(dossier, logs, 1, "b")
        res["panne_api"] = test_panne_api(dossier, logs)
        res["ollama_injoignable"] = test_ollama_injoignable(dossier, logs)
        res["catalogue_json_invalide"] = test_catalogue(dossier, logs, "a", corrompre_virgule)
        res["catalogue_allergene_retire"] = test_catalogue(dossier, logs, "b", corrompre_allergene)
        res["confidentialite"] = test_confidentialite(logs)

    reference = {}
    if res["reference"]:
        with open(args.reference, encoding="utf-8") as f:
            reference = json.load(f)
    with open(os.path.join(sortie, "resultats.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    with open(os.path.join(sortie, "rapport.md"), "w", encoding="utf-8") as f:
        f.write(rapport(res, reference))
    print(f"\nTerminé : {os.path.relpath(sortie, PROJET)}/rapport.md et resultats.json")


if __name__ == "__main__":
    main()
