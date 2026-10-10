# Journal des corrections — Sobriété et fiabilité

Ce journal suit les corrections faites après les mesures AVANT (`mesures/avant/analyse_avant.md`), dans la branche `feat/observability`. Pour chaque étape : le problème visé (identifiants du rapport d'audit), ce qui a été modifié, et le test qui prouve que la correction fonctionne. Les mesures chiffrées APRÈS (consommation, charge, pannes) seront refaites une fois toutes les corrections terminées.

## B1 — Journalisation structurée sans données personnelles

**Problèmes visés :** F1 (erreurs avalées sans trace), F8 (pas de journalisation structurée), C12 (données personnelles dans les logs).

**Commit :** `f1f8e37` — *Add structured JSON logging without personal data*

**Ce qui a été modifié :**

- Nouveau module `observability.py` : un logger qui écrit une ligne JSON par événement (horodatage, niveau, nom de l'événement, `request_id`, champs techniques). Les erreurs incluent la trace complète.
- `app.py` : un middleware attribue un `request_id` de 8 caractères à chaque requête, enregistre l'événement `http_request` (méthode, chemin, code HTTP, durée) et renvoie l'en-tête `X-Request-ID`.
- `chatbot.py` : le `print` qui affichait le message du client est remplacé par l'événement `chat_message` (8 premiers caractères de la session et longueur du message uniquement). Chaque appel au modèle produit `llm_call` (modèle, tokens, latence) ; en cas d'échec, `llm_call_failed` (niveau ERROR, type et cause de l'erreur, trace).
- Règle : aucun contenu de message, aucune allergie et aucune réponse ne sont transmis aux logs.

**Test APRÈS :**

| Vérification | Résultat |
|---|---|
| Message normal : événements `chat_message`, `llm_call`, `http_request` | ✅ présents, avec le même `request_id` (`f7a9b0f3`) |
| Contenu du message dans les logs | ✅ absent (seulement `message_length: 43`) |
| Tokens et latence de l'appel au modèle | ✅ `prompt_tokens: 717`, `completion_tokens: 247`, `latency_ms: 12717` |
| Panne simulée (`FAIL_RATE=1`) | ✅ ligne `"level": "ERROR"`, `"event": "llm_call_failed"`, `"detail": "Panne simulée : 503 service unavailable"`, trace pointant `chatbot.py:77` → `llm.py:21` |

**Comparaison avec AVANT (test 4) :** la panne n'apparaissait nulle part dans les logs et le diagnostic était impossible. Elle est maintenant visible, datée, expliquée et reliée à la requête concernée.

**Limites :** l'erreur n'est visible que pour quelqu'un qui lit le terminal (traité en B2) ; `/chat` répond toujours 200 et enregistre le message d'excuse dans l'historique (prévu en B7).

## B2 — Suivi des erreurs avec Sentry

**Problèmes visés :** F2 (aucun suivi d'erreurs ni alerte), F1.

**Commit :** `bf9dcd6` — *Add Sentry error tracking with privacy-safe settings*

**Ce qui a été modifié :**

- Compte Sentry (plan gratuit), projet FastAPI, **région de données UE (Allemagne)** : DSN en `ingest.de.sentry.io`. Seule la fonctionnalité *Error Monitoring* est activée (pas de tracing, profiling, logs ni session replay).
- `app.py` : `sentry_sdk.init(...)` avant la création de l'application, activé seulement si `SENTRY_DSN` est défini, avec des réglages qui protègent les données :
  - `send_default_pii=False` : pas d'adresse IP, de cookies ni d'en-têtes personnels envoyés par le SDK ;
  - `max_request_body_size="never"` : le corps des requêtes (message, allergies) n'est jamais envoyé ;
  - `include_local_variables=False` : les variables (prompt, historique) ne sont pas envoyées ;
  - `traces_sample_rate=0` : pas de suivi de performance (sobriété).
- Les erreurs journalisées en B1 (`log_event("error", ..., exc_info=True)`) sont transmises automatiquement grâce à l'intégration `logging` de Sentry ; les erreurs non gérées (HTTP 500) par l'intégration FastAPI.
- `SENTRY_DSN` dans `.env` (non versionné) ; `.env.example` documente la variable ; `requirements.txt` ajoute `sentry-sdk[fastapi]>=2.0`.

**Test APRÈS** (panne simulée avec `FAIL_RATE=1`, un message envoyé depuis le navigateur) :

| Vérification | Résultat |
|---|---|
| Erreur reçue par Sentry | ✅ issue `PYTHON-FASTAPI-1`, `RuntimeError: Panne simulée : 503 service unavailable`, niveau Error, priorité High |
| Diagnostic possible | ✅ trace `llm.py:21` (`chat`) ← `chatbot.py:77` (`handle_chat`), avec le code autour |
| Corps de la requête envoyé à Sentry | ✅ vide (`Body ""`) |
| Fil d'Ariane (breadcrumbs) | ✅ `chat_message` avec seulement 2 champs techniques |
| Données supplémentaires | ✅ `model`, `error`, `detail`, `latency_ms` uniquement |
| Utilisateur identifié | ✅ aucun (Users : 0) |

**Points en attente :**

- **Géolocalisation** : Sentry affiche « Denain, France », déduite de l'adresse IP d'envoi. À désactiver dans les réglages du projet (« Prevent Storing of IP Addresses »).
- **Informations techniques du navigateur** (Firefox, Ubuntu) issues de l'en-tête User-Agent : non sensibles, mais à mentionner.
- **Alerte e-mail** : à confirmer, avec le délai entre la panne et la réception (« délai de détection » pour le comparatif ; AVANT : jamais).
- **Capture d'écran** de l'issue (corps vide et données supplémentaires) à ajouter comme preuve.

## B3 — Réponses fixes (FAQ) et cache du premier message

**Problèmes visés :** S1 (gros modèle pour des questions simples), S6 (pas de cache), C9 (informations inventées : 9 conversations, 9 horaires différents dans les mesures AVANT).

**Commit :** `faeafc9` — *Add fixed FAQ answers and first-message cache to avoid needless LLM calls*

**Ce qui a été modifié :**

- Nouveau fichier `data/faq.json` : réponses fixes pour les horaires et la livraison, avec leurs mots-clés. Le contenu est séparé du code pour que la Maison Delcourt puisse le modifier. Les réponses n'inventent aucun horaire : elles renvoient vers le site (texte à valider par la Personne A et le client).
- `chatbot.py` :
  - `find_faq()` : si le message fait 8 mots au plus et contient un mot-clé, la réponse fixe est renvoyée sans appeler le modèle (événement `faq_hit`). Au-delà de 8 mots, il s'agit d'une vraie demande et le modèle répond.
  - Cache du **premier message** d'une conversation : la clé associe le message normalisé et la liste des allergies. Une réponse déjà calculée est réutilisée (événement `cache_hit`). Le cache est limité à 200 entrées, ne garde que des réponses réussies (jamais un message d'erreur) et reste **en mémoire** (rien n'est écrit sur disque, tout disparaît au redémarrage).

**Test APRÈS** (logique testée sur une copie isolée avec un faux modèle, puis dans le navigateur) :

| # | Cas | Résultat attendu | Résultat |
|---|---|---|---|
| 1 | « Quels sont vos horaires ? » | réponse fixe, 0 appel au modèle | ✅ |
| 2 | « Livraison ? » | réponse fixe, 0 appel | ✅ |
| 3 | Phrase longue parlant de livraison | envoyée au modèle | ✅ |
| 4 | 1er message, conversation A, « Un coffret à 30 euros » | appel au modèle, réponse mise en cache | ✅ |
| 5 | Même 1er message, conversation B, mêmes allergies | `cache_hit`, 0 appel | ✅ |
| 6 | Même message avec d'autres allergies | appel au modèle (pas de mélange entre allergies) | ✅ |
| 7 | Même message en 2e position d'une conversation | appel au modèle (le cache ne vaut que pour le 1er message) | ✅ |

**Gain attendu :** dans le scénario de mesure, 6 messages sur 15 (40 %) sont des questions d'horaires, désormais traitées sans modèle. Le cache n'apparaîtra presque pas dans les mesures (le premier message de chaque conversation du scénario est déjà une question d'horaires) ; il sert surtout en conditions réelles, quand beaucoup de clients cliquent sur les mêmes suggestions.

**Limite :** le texte des messages sert de clé au cache ; il reste en mémoire seulement, le temps de vie du serveur.

## B4 — Petit modèle pour la politesse et les confirmations

**Problème visé :** S1 (le gros modèle répond à tout ; le petit modèle `llama3.2:1b`, configuré, n'était jamais utilisé).

**Commit :** `38de6d9` — *Route politeness and confirmation messages to the small model*

**Ce qui a été modifié :**

- `chatbot.py` : nouvelle fonction `choose_model()`. Le petit modèle (`llm.SMALL_MODEL`) répond seulement si le message **commence par une formule de politesse ou de confirmation** (merci, ok, oui, non, parfait, super, d'accord, bonjour, bonsoir, salut, au revoir) **et** ne contient **aucun mot à risque** (allergie, euro, prix, budget, enfant, cadeau, conseil, recommandation). Dans tous les autres cas, et en cas de doute, c'est le gros modèle qui répond.
- Le modèle choisi est utilisé pour l'appel et apparaît dans les logs (`llm_call`, et `llm_call_failed` en cas d'erreur).

**Test APRÈS :**

1. Logique testée sur une copie isolée avec un faux modèle (13 messages) :

| Message | Modèle choisi |
|---|---|
| « Merci, je prends le coffret sans noix ! » | 1b ✅ |
| « Oui », « D'accord », « Parfait », « Au revoir », « Okay merci » | 1b ✅ |
| « Bonjour, je cherche un coffret pour 30 euros » | 3b ✅ (mot « euros ») |
| « Merci ! Et pour mon fils allergique ? » | 3b ✅ (mot « allergique », malgré « merci ») |
| « Super, un cadeau pour ma mère ? » | 3b ✅ (mot « cadeau », malgré « super ») |
| « Et pour les enfants, vous avez quoi ? », « Un coffret à 30 euros », « Du chocolat noir intense », « Noir ou lait ? » | 3b ✅ |

2. Avec les vrais modèles, dans le navigateur :

| Message | Modèle | Tokens (entrée / sortie) | Latence |
|---|---|---|---|
| « Un coffret à 30 euros » | `llama3.2:3b` ✅ | 1 191 / 336 | 16,9 s |
| « Merci, je prends le coffret sans noix ! » | `llama3.2:1b` ✅ | 1 549 / 158 | 7,9 s |

**Qualité de la réponse du petit modèle :** cohérente. Il confirme le bon coffret (Sans Noix, 28 €) et ne fabrique plus de fausse commande, de faux e-mail de confirmation ni de livraison, contrairement aux réponses de fin de conversation mesurées AVANT. Il reprend en revanche une composition inventée (« 12 tranches de ganache vanille… ») présente dans la réponse précédente du gros modèle.

**Gain attendu :** dans le scénario de mesure, les 3 messages « Merci, je prends le coffret sans noix ! » passent au petit modèle. Avec la FAQ (B3), les appels au gros modèle devraient passer de 15 à 6 par exécution (−60 %).

**Limites et observations :**

- Les latences ci-dessus sont celles d'un premier appel (modèle chargé en mémoire) et ne sont pas représentatives ; les mesures APRÈS avec `mesure.py` (qui préchauffe les deux modèles) feront foi.
- Le prompt du petit modèle reste long (1 549 tokens) car il reçoit tout l'historique et le catalogue : ce sera traité par la réduction de l'historique et du prompt (B5, B6).
- Le gros modèle invente encore des compositions (« 12 tranches… », « 6 pralines ») : la consigne « détaillée et complète » du prompt sera revue en B5.
- La règle est volontairement prudente : elle laisse au gros modèle tout message qui ressemble à une demande de conseil.

## B5 — Réponses courtes et moins d'inventions

**Problèmes visés :** S2 (réponses longues : consigne « détaillée et complète », `max_tokens=1500`), S8 (température élevée), C9 (informations inventées : compositions, quantités, fausses commandes).

**Commit :** `6a11778` — *Shorten answers and reduce hallucinations: concise prompt, 300-token cap, lower temperature*

**Ce qui a été modifié :**

- `chatbot.py`, consigne du modèle : « détaillée et complète, en présentant plusieurs options » est remplacé par « chaleureuse et concise : 3 à 4 phrases au maximum, et 2 coffrets au plus », avec deux nouvelles règles : ne pas inventer de composition, de quantité ni de prix ; ne prendre aucune commande et n'annoncer ni e-mail ni livraison (renvoyer vers le site).
- `chatbot.py` : `MAX_TOKENS = 300` remplace `max_tokens=1500`. C'est un filet de sécurité : la longueur est pilotée par la consigne (3 à 4 phrases, soit environ 100 à 150 tokens), la limite évite seulement les dérapages.
- `llm.py` : `temperature` passe de 0,7 à 0,3 pour des réponses plus stables.

**Test APRÈS** (navigateur, même scénario qu'en B4) :

| Message | Modèle | Tokens de sortie | Avant B5 | Latence |
|---|---|---|---|---|
| « Un coffret à 30 euros » | 3b | **135** | 336 (test B4) ; 205 en moyenne AVANT | 10,0 s |
| « Merci, je prends le coffret sans noix » | 1b | **46** | 158 (test B4) | 5,6 s |

| Vérification | Résultat |
|---|---|
| Au plus 2 coffrets proposés | ✅ Sans Noix (28 €) et Beffroi (24 €) |
| Prix conformes au catalogue | ✅ |
| Compositions reprises du catalogue, sans quantité inventée | ✅ (plus de « 12 tranches… ») |
| Pas de fausse commande, d'e-mail ni de livraison annoncés | ✅ |
| Réponse coupée au milieu d'une phrase | ✅ aucune |

**Observations :**

- La réponse du gros modèle commence par « Bonjour ! Je serais ravi de vous aider » **sans se présenter comme assistant virtuel (IA)**, alors que la consigne le demande. Point signalé à la Personne A (transparence AI Act) ; l'étiquette de l'interface reste la garantie principale.
- La réponse du petit modèle reste courte et sans fausse commande, mais suggère de « remplir » le coffret avec certaines ganaches, ce qui laisse croire à une personnalisation qui n'existe pas.
- Le test ne porte que sur un message de chaque type : les moyennes viendront des mesures APRÈS avec `mesure.py`.

## B6 — Historique limité et catalogue compact

**Problèmes visés :** S3 (tout l'historique renvoyé à chaque message, prompt qui grossit sans limite), S5 (catalogue complet en JSON dans chaque requête).

**Commit :** `3719d94` — *Limit history to last 6 messages and send a compact catalog*

**Ce qui a été modifié :**

- `chatbot.py` : `HISTORY_MAX = 6` ; seuls les 6 derniers messages de la conversation (3 échanges, message en cours compris) sont envoyés au modèle. La conversation complète reste utilisée pour savoir s'il s'agit du premier message (cache B3).
- `chatbot.py` : nouvelle fonction `format_catalog()` ; le catalogue (déjà filtré selon les allergies) est envoyé sous forme d'une ligne par coffret (nom, prix, contenu, allergènes) au lieu du JSON complet (identifiants, étiquettes, espaces).
- Couper l'historique est sans risque pour les allergies : elles accompagnent chaque message et le catalogue est filtré dans le code (correction A2), donc un coffret dangereux n'est jamais transmis au modèle, même s'il a « oublié » le début de la conversation.

**Test APRÈS :**

1. Logique vérifiée avec un faux modèle : au 5e message, exactement 6 messages d'historique envoyés, le dernier étant le message en cours ; avec l'allergie « fruits à coque », seuls les 3 coffrets compatibles figurent dans le catalogue envoyé.
2. Conversation de 5 messages dans le navigateur (aucune allergie cochée), gros modèle à chaque fois :

| # | Message | Tokens d'entrée | Tokens de sortie | Latence |
|---|---|---|---|---|
| 1 | « Un coffret à 30 euros » | **504** (766 en B5) | 130 | 8,5 s |
| 2 | « et en chocolat noir ? » | 649 | 95 | 3,1 s |
| 3 | « et pour un enfant ? » | 759 | 93 | 2,1 s |
| 4 | « plutot moins cher ? » | 855 | 83 | 3,5 s |
| 5 | « et pour qui aime des fruits ? » | **809** | 92 | 3,5 s |

- **Catalogue compact :** le premier message passe de 766 à 504 tokens d'entrée (−34 %).
- **Historique limité :** le prompt cesse de grossir à partir du 4e message (855 puis 809), au lieu d'augmenter à chaque échange.
- **Cohérence de la conversation :** conservée. Le modèle comprend « plutôt moins cher » dans le contexte « pour un enfant », et tous les prix cités sont conformes au catalogue (28 €, 59 €, 32 €, 14 €, 18 €).

**Observations sur la qualité (hors périmètre B6) :**

- « Un coffret à 30 euros » est compris comme « exactement 30 € » (« je n'ai pas de coffret à 30 euros ») et le Grand Coffret Noël à 59 € est proposé, bien au-dessus du budget.
- À « plutôt moins cher ? », après le coffret à 14 €, le modèle propose celui à 18 € : erreur de raisonnement sur les prix.
- Le modèle ne se présente toujours pas comme assistant virtuel (IA) dans sa première réponse (signalé à la Personne A).
- La latence du 1er message (8,5 s) correspond au chargement du modèle ; les suivantes sont entre 2 et 3,5 s.

## B7 — Résilience : nouvelle tentative, modèle de secours, réponse fixe

**Problèmes visés :** F4 (aucune nouvelle tentative ni solution de repli), F5 (délai d'attente de 180 s), F9 (message d'erreur enregistré dans l'historique), S8 (client HTTP recréé à chaque appel).

**Commit :** `407a66e` — *Add retry with small-model fallback, fixed reply on failure, 30s timeout and no hidden retries*

**Ce qui a été modifié :**

- `llm.py` : un seul client pour toute l'application, avec `timeout=30` et `max_retries=0`. Le client OpenAI refaisait jusqu'ici 2 tentatives cachées par défaut : avec l'ancien délai de 180 s, une requête pouvait rester bloquée jusqu'à 9 minutes sans aucune trace. Les nouvelles tentatives sont désormais visibles et gérées dans `chatbot.py`.
- `chatbot.py` : nouvelle fonction `call_model()`. Le modèle choisi (B4) est appelé ; en cas d'échec, le petit modèle prend le relais. Chaque échec intermédiaire est journalisé en `warning` (sans alerte) ; seul l'échec final est journalisé en `error` avec la trace, donc un seul événement Sentry par message. Le champ `attempt` indique quelle tentative a répondu.
- `chatbot.py` : si les deux tentatives échouent, le client reçoit une réponse fixe (« Désolé, je ne peux pas répondre pour le moment… consulter nos coffrets sur notre site »), qui **n'est pas enregistrée** dans l'historique.
- Compatibilité avec le travail de la Personne A : le cache stocke des couples (horodatage, réponse), format attendu par la purge du cache ajoutée sur `dev`.

**Test APRÈS :**

1. Logique vérifiée avec un faux modèle : modèle en panne → secours par le petit modèle ; tout en panne → réponse fixe non enregistrée ; un premier message déjà en cache reste servi **même pendant la panne**.
2. `FAIL_RATE=1` : réponse fixe ; dans les logs, `warning` (tentative 1, 3b) puis `error` (tentative 2, 1b). Dans Sentry, l'événement est rattaché à l'issue existante `PYTHON-FASTAPI-1` (même erreur, 7 événements), avec la trace `chatbot.py:83 in call_model`, les champs `attempt: 2` et `model: llama3.2:1b`, et la tentative 1 visible dans le fil d'Ariane. Corps de requête toujours vide.
3. `FAIL_RATE=0.3`, 12 messages :

| | Nombre |
|---|---|
| Réponses par la FAQ (sans modèle) | 2 |
| Messages nécessitant le modèle | 10 |
| → réponse à la 1re tentative | 8 |
| → **sauvés par le modèle de secours** | **1** (1,4 s au total) |
| → réponse fixe (les deux tentatives ont échoué) | **1** |

Sans B7, les 2 échecs en 1re tentative auraient donné 2 erreurs sur 10 (20 %) ; avec B7, 1 sur 10 (10 %), et le client reçoit un message poli. En théorie, avec 30 % d'échecs par appel et deux tentatives indépendantes, environ 9 % des messages finissent sur la réponse fixe (0,3 × 0,3).

4. **Ollama réellement arrêté** (`sudo systemctl stop ollama`) :

| Message | Résultat | Durée totale |
|---|---|---|
| Demande de conseil | 3b puis 1b en échec (`APIConnectionError`, « Connection refused ») → réponse fixe | 145 ms |
| « Livraison ? » | FAQ | 16 ms |
| Demande de conseil | réponse fixe | 55 ms |
| « Quels sont vos horaires ? » | FAQ | 21 ms |

**Comparaison avec AVANT (test 4) :** la panne était invisible, le message d'erreur était enregistré comme une vraie réponse et l'attente pouvait atteindre plusieurs minutes. Désormais, la cause est écrite dans les logs et envoyée à Sentry, le client reçoit une réponse polie en moins de 0,2 s, et la FAQ continue de fonctionner pendant la panne.

**Limites :**

- `/chat` répond toujours avec le code HTTP 200, même avec la réponse fixe ; c'est voulu pour l'interface, mais `/health` ne signale toujours pas la panne (prévu en B8).
- La règle d'alerte « nouvelle issue » ne se déclenche pas de nouveau pour une erreur déjà connue : la règle « plus de 5 événements en 5 minutes » reste nécessaire pour être prévenu d'une panne qui se répète.
- Le message du client reste enregistré sans réponse lorsque les deux tentatives échouent.

## B8 — Contrôle de santé réel (`/health`)

**Problème visé :** F3 (`/health` répondait toujours « ok », même avec le modèle hors service).

**Commit :** `ab6cfa7` — *Make /health check the database and model server, returning 503 when degraded*

**Ce qui a été modifié :**

- `llm.py` : nouvelle fonction `check_models()`. Elle interroge le serveur de modèles (liste des modèles, délai de 3 s seulement) et vérifie que le gros et le petit modèle sont bien installés.
- `app.py` : `/health` vérifie désormais deux choses : la base de données (`SELECT 1`) et le serveur de modèles (`check_models()`). Il répond **200** avec `{"status": "ok"}` si tout fonctionne, et **503** avec `{"status": "degraded"}` et le détail du composant en panne sinon.
- En cas d'échec, l'événement `health_check_failed` est journalisé en `warning` : `/health` peut être appelé très souvent (par un outil de surveillance), il ne doit pas déclencher une alerte Sentry à chaque appel. Les vraies pannes vues par les clients restent signalées par B2 et B7.
- La réponse ne contient aucune donnée personnelle ni secret (seulement l'état des composants et le nom de l'erreur).

**Test APRÈS** (route appelée directement, chaque cas dans un processus séparé, Sentry désactivé pendant le test) :

| Cas | Comment il a été provoqué | Code HTTP | Réponse |
|---|---|---|---|
| Tout fonctionne | Ollama démarré | **200** | `{"status": "ok", "checks": {"database": "ok", "llm": "ok"}}` |
| Serveur de modèles injoignable | `LLM_BASE_URL` pointant vers un port fermé | **503** | `llm : erreur : APIConnectionError (Connection error.)` |
| Modèle non installé | `LLM_MODEL_SMALL=modele-inexistant` | **503** | `llm : erreur : RuntimeError (modèle(s) absent(s) : modele-inexistant)` |
| Base de données inaccessible | connexion SQLite fermée | **503** | `database : erreur : ProgrammingError (Cannot operate on a closed database.)` |

Vérification de bout en bout avec un vrai serveur (port 8765) : `GET /health` → **200** quand tout fonctionne, **503** quand le serveur de modèles est injoignable. Le log contient alors `health_check_failed` (niveau WARNING) puis `http_request` avec `status: 503`. Chaque contrôle prend entre 10 et 25 ms.

**Comparaison avec AVANT (test 4) :** pendant une panne totale du modèle, `/health` répondait `{"status":"ok"}` avec le code 200. Il signale maintenant la panne (503) et indique quel composant est en cause.

**Limites :**

- `/health` ne fait que décrire l'état : pour être prévenu automatiquement, il faudrait qu'un outil externe l'appelle à intervalle régulier (par exemple un moniteur de disponibilité, ou les *Uptime Monitors* de Sentry) et alerte en cas de 503.
- La route est publique et indique les noms des modèles en cas d'absence : information technique mineure, à restreindre en production si nécessaire.

## B9 — Validation du catalogue au démarrage

**Problème visé :** F6 (catalogue chargé sans aucun contrôle). Mesures AVANT : une virgule manquante empêchait le serveur de démarrer avec une trace illisible de 75 lignes (test 5a) ; un allergène supprimé passait inaperçu et le Coffret Beffroi était proposé à une personne allergique dans 2 réponses sur 3 (test 5b).

**Commit :** à compléter

**Ce qui a été modifié :**

- `chatbot.py` : le catalogue est lu par `charger_catalogue()`, puis vérifié par `valider_catalogue()` :
  - **format** (modèle Pydantic `Coffret`) : identifiant du type `C01`, nom non vide, prix numérique strictement positif, contenu non vide, liste d'allergènes ;
  - **identifiants uniques** ;
  - **allergènes connus** : chaque allergène doit correspondre à une catégorie gérée par le filtre (lait, fruits à coque, gluten, œuf, soja, arachides) ;
  - **cohérence contenu / allergènes** : si le contenu mentionne un ingrédient allergène (par exemple « praliné noisette »), la catégorie correspondante (« fruits à coque ») doit être déclarée.
- Si le catalogue est invalide, **aucun coffret n'est utilisé** : le serveur démarre quand même, la FAQ continue de fonctionner, mais toute demande de conseil reçoit une réponse fixe (« Nos conseils personnalisés sont momentanément indisponibles… »), sans appel au modèle et sans enregistrement dans l'historique. Le chatbot ne conseille jamais à partir de données fausses.
- `app.py` : au démarrage, l'événement `catalog_invalid` (niveau ERROR, donc envoyé à Sentry) liste chaque problème avec un message lisible. Il est émis après `sentry_sdk.init` pour que l'alerte parte bien.
- `app.py` : `/health` vérifie aussi le catalogue et répond 503 s'il est invalide (`"catalogue": "erreur : 1 problème(s), voir les logs"`).
- `CATALOG_PATH` (variable d'environnement facultative) permet d'indiquer un autre fichier de catalogue, ce qui a servi à tester des catalogues corrompus sans toucher au vrai.

**Test APRÈS :**

1. Validation de 7 catalogues de test (copies du vrai catalogue modifiées volontairement, créées hors du projet) :

| Catalogue testé | Message obtenu | Coffrets utilisés |
|---|---|---|
| Catalogue réel | aucun problème | 7 |
| 5a : virgule supprimée | `JSON invalide ligne 3, colonne 3 : Expecting ',' delimiter (l'erreur peut se trouver à la fin de la ligne précédente)` | 0 |
| 5b : « fruits à coque » retiré du Coffret Beffroi | `C01 (Coffret Beffroi) : le contenu mentionne « noisette » mais l'allergène « fruits a coque » n'est pas déclaré` | 0 |
| Allergène inconnu | `C02 : allergène inconnu « sésame »` | 0 |
| Champ manquant et identifiant en double | `C03 : champ « contenu » : Field required` ; `C01 : identifiant en double` | 0 |
| Prix invalides | `C04 : champ « prix » : Input should be a valid number…` ; `C05 : champ « prix » : Input should be greater than 0` | 0 |
| Catalogue vide | `le catalogue doit être une liste non vide de coffrets` | 0 |
| Fichier absent | `fichier introuvable : …` | 0 |

2. Comportement du chatbot avec le catalogue 5b (faux modèle) : demande de conseil → réponse fixe, **0 appel au modèle**, réponse non enregistrée ; question d'horaires → FAQ normale.

3. De bout en bout avec un vrai serveur (port 8765, Sentry désactivé pendant le test) :

| Catalogue | Démarrage | `/health` | Demande de conseil | « Livraison ? » |
|---|---|---|---|---|
| 5b (allergène retiré) | ✅ démarre ; log `catalog_invalid` avec le message ci-dessus | **503** | réponse fixe | FAQ ✅ |
| 5a (virgule supprimée) | ✅ démarre ; log `catalog_invalid` (JSON invalide ligne 3) | **503** | — | — |
| Catalogue réel | ✅ aucun `catalog_invalid` | **200** | — | — |

**Comparaison avec AVANT :**

| | AVANT | APRÈS |
|---|---|---|
| Virgule manquante (5a) | serveur arrêté, trace de 75 lignes, aucune alerte | serveur disponible (FAQ), message d'une ligne qui cite le fichier et la position, alerte Sentry, `/health` en 503 |
| Allergène supprimé (5b) | non détecté ; Beffroi proposé à un allergique 2 fois sur 3 | détecté au démarrage, aucun conseil donné à partir de ce catalogue, alerte Sentry, `/health` en 503 |

**Limites :**

- Le contrôle de cohérence repose sur la liste de mots de `ALLERGEN_ALIASES` : un ingrédient allergène absent de cette liste (par exemple « sésame », « praliné » seul) ne serait pas repéré. Ajouter un nouvel allergène au catalogue impose aussi de l'ajouter à cette liste (c'est le sens du message « allergène inconnu »).
- Le catalogue est lu au démarrage : après une correction du fichier, il faut redémarrer le serveur.
- La validation ne détecte pas une erreur « plausible » (par exemple un prix modifié de 28 € à 26 €).

## Mesures APRÈS (tests automatisés)

**Outil :** nouveau script `tests_auto.py`, qui rejoue en une commande tous les tests de la phase 1 (consommation avec `mesure.py` ×3, bout en bout, pics de charge 3a et 3b, panne de l'API, serveur de modèles injoignable, catalogue corrompu 5a et 5b) et vérifie en plus qu'aucun texte de client n'apparaît dans les logs. Le code est copié dans un dossier temporaire : la base et le catalogue du projet ne sont jamais modifiés ; les serveurs de test tournent sur le port 8765, Sentry désactivé. Résultats : `mesures/apres/resultats.json`, `mesures/apres/rapport.md` et les logs des serveurs. La référence AVANT est `mesures/avant/resultats.json` (valeurs de `analyse_avant.md` au même format).

Préparation : `load_test.py` accepte une autre adresse de serveur (`CHOCOBOT_URL`) et envoie `privacy_consent` ; `mesure.py` transmet les allergies (« fruits à coque ») et compte aussi les recommandations dangereuses à la question sur les enfants.

Utilisation pour une version future :

```bash
python tests_auto.py --label v2 --rapide                                   # pannes et catalogue (≈ 1 min)
python tests_auto.py --label v2 --reference mesures/apres/resultats.json   # tout, comparé à cette série (≈ 5 min)
```

**Résultats** (8 octobre 2026, code `2e856f2`, 2e série complète ; la 1re série donne des valeurs très proches) :

| Indicateur | AVANT | APRÈS | Écart |
|---|---|---|---|
| Appels au modèle (15 messages) | 15 | 9 | −40 % |
| Part du gros modèle | 100 % | 40 % | |
| Tokens d'entrée / message | 1 225 | 298 | −76 % |
| Tokens de sortie / message | 205 | 27 | −87 % |
| Tokens totaux (15 messages) | 21 461 | 4 874 | **−77 %** |
| Latence moyenne / p95 | 5,5 s / 8,2 s | 2,3 s / 6,7 s | −58 % / −19 % |
| Longueur moyenne des réponses | 748 car. | 180 car. | −76 % |
| Énergie / message | 0,099 Wh | 0,027 Wh | **−72 %** |
| CO₂e (15 messages) | 82,9 mg | 22,9 mg | −72 % |
| `load_test.py 2` (10 messages) | 55,1 s | 27,4 s | −50 % |
| Pic échelonné (3b) : clients terminés / erreurs | 5/5 / 0 | 5/5 / 0 | |
| Pic échelonné (3b) : temps par message vu par un client | 29,2 s | 5,3 s | −82 % |
| Pic simultané (3a) : clients terminés / erreurs 500 | 3/5 / 2 | **2/5 / 3** (1re série : 1/5 / 4) | régression |
| Panne API : erreur journalisée / cause visible | non / non | oui / oui | |
| Panne API : messages d'erreur enregistrés comme réponses | 3 | 0 | |
| Serveur de modèles injoignable : `/health` | 200 | 503 (réponse fixe en 0,05 s, FAQ disponible) | |
| Catalogue JSON invalide (5a) : serveur démarre / erreur signalée | non / non | oui / oui (`/health` 503) | |
| Allergène retiré (5b) : détecté / Beffroi proposé | non / oui | oui / non (`/health` 503) | |
| Textes de clients dans les logs | profil complet | aucun (7 logs vérifiés) | |

**Recommandations dangereuses, vérification à la main :** les 18 réponses aux questions « allergie » et « enfants » ont été relues. Aucune ne propose un coffret contenant des fruits à coque (seulement Sans Noix, Ch'ti Noir et Gaufre de Lille), contre 4/9 et 12/18 AVANT. Le filtrage dans le code (A2) rend ce résultat stable.

**Points d'attention révélés par les mesures :**

- **Régression du pic simultané (3a).** La connexion SQLite partagée par toutes les requêtes (`db.py`, problème F7) n'a pas été corrigée, et la purge automatique ajoutée à chaque enregistrement de message multiplie les accès simultanés à la base ; des réponses plus rapides augmentent aussi les chevauchements. Les erreurs sont des `sqlite3.InterfaceError`. Correction proposée : protéger les accès à la base par un verrou (`threading.Lock`) ou ouvrir une connexion par requête dans `db.py` (fichier de la Personne A).
- **Refus injustifiés (E7).** Le modèle affirme parfois que tous les coffrets contiennent des noisettes, alors que le catalogue qu'il reçoit est déjà filtré. C'est sans danger mais faux et peu utile. Piste : préciser dans la consigne que les coffrets listés sont déjà compatibles avec les allergies indiquées.
- **Budget :** un coffret à 32 € reste proposé pour un budget de 30 € (E8).
- Les tests de pannes simulées (`FAIL_RATE`) ne touchent que l'appel au modèle : `/health` reste à 200 dans ce cas ; la vraie indisponibilité du serveur de modèles est couverte par le test 4b.

## Erreurs qui persistent (exemples relevés pendant les tests)

Exemples relevés dans les réponses du chatbot pendant les tests des corrections (8 octobre 2026). Les conversations d'origine ne sont plus en base (purge automatique après inactivité) ; les extraits sont recopiés tels quels.

| # | Relevé pendant | Modèle | Type d'erreur | Message du client | Extrait de la réponse | Ce qui est faux |
|---|---|---|---|---|---|---|
| E1 | B4 | 3b | Quantités inventées | « Un coffret à 30 euros » | « Coffret Sans Noix : Ce coffret est composé de 12 tranches de ganache vanille, 6 framboises et 6 pièces de menthe » | Le catalogue ne donne aucune quantité (corrigé en B5 : plus observé ensuite) |
| E2 | B4 | 1b | Reprise d'une invention | « Merci, je prends le coffret sans noix ! » | « Le coffret contient 12 tranches de ganache vanille, 6 framboises et 6 pièces de menthe. » | Le petit modèle répète l'invention du gros modèle présente dans l'historique |
| E3 | B5, B6 | 3b | Pas de présentation comme IA | « Un coffret à 30 euros » | « Bonjour ! Je serais ravi de vous aider à choisir un coffret… » / « Je suis ravie de vous aider à trouver le coffret parfait ! » | La consigne demande de se présenter comme assistant virtuel (IA) (AI Act, art. 50) |
| E4 | B5 | 1b | Personnalisation inventée | « Merci, je prends le coffret sans noix » | « Je vous recommande de le remplir avec des ganaches vanille et framboise » | Les coffrets ne sont pas personnalisables |
| E5 | B6 | 3b | Budget mal compris | « Un coffret à 30 euros » | « Malheureusement, je n'ai pas de coffret à 30 euros dans notre catalogue. […] Ou bien, le Grand Coffret Noël, qui est à 59 euros » | « 30 euros » compris comme « exactement 30 € » ; coffret proposé à près du double du budget |
| E6 | B6 | 3b | Raisonnement sur les prix | « plutot moins cher ? » (après le Mendiants des Enfants à 14 €) | « Un coffret moins cher pour un enfant ! Le Coffret Gaufre de Lille […] il est à 18 euros » | 18 € est plus cher que 14 € |
| E7 | Mesures APRÈS | 3b | Refus injustifié | « Je cherche un coffret pour 30 euros, mon fils est allergique aux noisettes. » | « Malheureusement, nous n'avons pas de coffret qui convient à votre fils, car tous nos coffrets contiennent des noisettes. » | Faux : le catalogue envoyé (déjà filtré) contient 3 coffrets sans fruits à coque. Observé dans 1 réponse sur 9 lors de la 1re série, 5 sur 9 lors de la 2e |
| E8 | Mesures APRÈS | 3b | Budget dépassé | même message (budget 30 €) | « Le Coffret Sans Noix (28 €) et le Coffret Ch'ti Noir (32 €) sont sans noisettes. » | Coffret proposé au-dessus du budget annoncé |

**Ce que ces exemples montrent :**

- Les erreurs les plus graves des mesures AVANT (allergènes, fausses commandes, horaires inventés) ne réapparaissent plus dans ces tests, grâce au filtrage des allergènes (A2), à la FAQ (B3) et à la nouvelle consigne (B5).
- Il reste des erreurs de **raisonnement** (budget, comparaison de prix) et de **transparence** (présentation comme IA), que la consigne seule ne suffit pas à corriger. Pistes : afficher le message d'accueil « assistant virtuel (IA) » dans l'interface plutôt que de compter sur le modèle (Personne A) ; filtrer aussi le catalogue par budget dans le code, comme pour les allergies.

## À faire avant les mesures APRÈS

- ✅ `mesure.py` transmet les allergies à `handle_chat` (« fruits à coque »).
- ✅ `load_test.py` envoie `privacy_consent: true` et accepte l'adresse du serveur via `CHOCOBOT_URL`.
