Voici ton texte pour l'oral. Pour chaque diapositive, il y a deux parties :
- 🎤 À dire : le texte à prononcer, calé sur le temps prévu.
- 🧠 Pour comprendre : ce qu'il y a derrière, pour que tu saches exactement de quoi tu parles si on te pose une question. Ce n'est pas à dire.

J'ai vérifié les chiffres et le fonctionnement dans le code et dans mesures/apres/rapport.md. Il faut corriger une phrase de la diapositive 5 que je t'avais donnée : j'avais écrit « petit modèle par défaut », mais le code fait l'inverse. C'est expliqué dans la diapositive 5 ci-dessous.

---

Diapositive 3 : Le cadre légal (≈ 1 min 30)

🎤 À dire

▎ « Avant de corriger, nous avons regardé quelles règles s'appliquent à ChocoBot. Il y en a quatre.
▎
▎ D'abord le RGPD. Le point le plus sensible, ce sont les allergies : une allergie dit quelque chose de la santé d'une personne, donc c'est une donnée de santé, protégée par l'article 9. Son traitement est interdit par principe, sauf exceptions, comme le consentement explicite. À cela s'ajoutent les principes de l'article 5 : ne collecter que le nécessaire et ne pas garder les données plus longtemps qu'utile.
▎
▎ Ensuite l'AI Act, le règlement européen sur l'IA. Il classe les systèmes par niveau de risque. ChocoBot n'entre dans aucun des domaines à haut risque de l'annexe III : il vend des chocolats, il ne recrute personne et n'accorde pas de crédit. C'est donc un système à risque limité. Sa principale obligation est la transparence (article 50) : l'utilisateur doit savoir qu'il parle à une IA.
▎
▎ Ce règlement a été modifié cet été par le règlement Omnibus 2026/1744, en vigueur depuis le 27 juillet 2026. Pour nous, la date à retenir est le 2 décembre 2026, l'échéance pour marquer les textes générés par l'IA.
▎
▎ Enfin, la licence du modèle Llama 3.2 que nous utilisons impose ses propres règles : afficher « Built with Llama » et ne jamais faire passer les réponses pour celles d'un humain. »

🧠 Pour comprendre

- Ce que veut dire « donnée de santé » (art. 4.15 et 9 du RGPD). Toute information sur la santé physique ou mentale d'une personne. « Mon fils est allergique aux noisettes » en est une, même dans un chat de chocolaterie. L'article 9.1 en interdit le traitement, et l'article 9.2 liste les exceptions. Pour un commerce, la seule exception utilisable est le consentement explicite pour une finalité précise (9.2.a).
- Comment c'est fait dans ChocoBot. Les cases allergènes sont facultatives. Elles servent seulement, au moment du message, à retirer du catalogue les coffrets incompatibles avant que le modèle ne les voie (fonction filter_catalog). Elles ne sont jamais enregistrées dans la base.
- Les principes de l'article 5 : finalité précise (5.1.b), minimisation (5.1.c), durée de conservation limitée (5.1.e), sécurité (5.1.f) et responsabilité, c'est-à-dire savoir le prouver (5.2).
- La base légale de la conversation elle-même : l'article 6.1.b, des « mesures précontractuelles » à la demande du client. Le client demande un conseil avant d'acheter.
- Pourquoi l'article 22 (décision automatisée) ne s'applique pas (question possible du jury) : l'article 22 vise une décision entièrement automatisée qui produit des effets juridiques ou affecte la personne de manière similaire, comme un refus de crédit ou d'embauche. ChocoBot propose des coffrets, mais c'est le client qui décide.
- Les 4 niveaux de l'AI Act :
  a. inacceptable : pratiques interdites (art. 5), comme la manipulation ou la notation sociale ;
  b. haut risque (art. 6 + annexes I et III) ;
  c. risque limité : obligations de transparence (art. 50) ;
  d. risque minimal : aucune obligation.
- Les 8 domaines de l'annexe III :
  a. biométrie ;
  b. infrastructures critiques ;
  c. éducation ;
  d. emploi ;
  e. services essentiels (crédit, assurance santé/vie, secours) ;
  f. répression ;
  g. migration ;
  h. justice et démocratie.

  Le seul qu'on pourrait discuter est le 5, à cause des allergies. Il ne s'applique pas : vendre du chocolat n'est pas un service essentiel.
- Les deux obligations de l'article 50 qui nous concernent :
  - 50.1 : informer que l'utilisateur interagit avec une IA ;
  - 50.2 : marquer les contenus générés pour qu'ils soient détectables comme artificiels.

  Considérer que le 50.2 vaut aussi pour les réponses texte d'un chatbot, c'est notre lecture du texte. Le document de veille le présente comme une interprétation.
- Ce que l'Omnibus (UE) 2026/1744 a changé (adopté le 8.7.2026, publié au JO le 24.7.2026, en vigueur le 27.7.2026) :
  - les obligations « haut risque » sont repoussées au 2.12.2027 (annexe III) et au 2.8.2028 (annexe I) ;
  - pour les systèmes mis sur le marché avant le 2.8.2026, comme ChocoBot, le marquage de l'article 50.2 doit être fait au plus tard le 2.12.2026 ;
  - l'article 4 (culture de l'IA) passe de « garantir un niveau suffisant » à « favoriser » : c'est devenu une obligation de moyens et non plus de résultat.
- Les sanctions :
  - RGPD (art. 83) : jusqu'à 20 M€ ou 4 % du chiffre d'affaires mondial. En France, la CNIL a aussi une procédure simplifiée pour les affaires sans difficulté particulière : amende jusqu'à 20 000 €, décidée par le président de la formation restreinte seul.
  - AI Act (art. 99) : un manquement à la transparence peut coûter jusqu'à 15 M€ ou 3 %, et les PME bénéficient du montant le plus bas des deux.
- Les rôles : Meta est le fournisseur du modèle (Llama). La Maison Delcourt utilise ce modèle dans son propre outil, sous son nom : elle est donc déployeur, et selon la lecture, aussi fournisseur du système ChocoBot.
- La licence Llama 3.2 :
  - mention « Built with Llama » visible ;
  - copie de la licence fournie ;
  - politique d'utilisation : ne pas présenter les réponses comme écrites par un humain, ne pas donner de conseil médical, ne pas traiter de données sensibles sans droit.

  La restriction pour l'UE ne concerne que les modèles multimodaux (vision), pas le 1B et le 3B que nous utilisons. La mention « Built with Llama » n'est pas encore faite : elle figure dans « ce qui reste à faire ».

---

Diapositive 5 : Sobriété (≈ 1 min)

⚠️ Correction à faire sur la diapositive : remplace « Petit modèle par défaut, gros modèle seulement quand c'est nécessaire » par « Petit modèle pour les messages simples (merci, bonjour, ok), gros modèle pour tout conseil ». Le code (choose_model) utilise le gros modèle par défaut, et le petit seulement pour la politesse.

🎤 À dire

▎ « Pour la sobriété, notre idée était simple : la requête la plus sobre est celle qu'on n'envoie pas au modèle, et quand on l'envoie, on lui envoie le moins de texte possible.
▎
▎ D'abord, les questions fréquentes comme les horaires ou la livraison reçoivent une réponse fixe, sans appeler l'IA. C'est instantané, ça ne consomme rien, et c'est plus fiable : avant, le bot inventait parfois des horaires.
▎
▎ Ensuite, un cache : si le premier message d'une conversation a déjà reçu une réponse, on la réutilise.
▎
▎ Puis le choix du modèle : un « merci » ou un « bonjour » part vers le petit modèle. Dès qu'il est question d'allergie, de budget ou d'enfant, on garde le gros modèle, parce que la sécurité passe avant l'économie.
▎
▎ Enfin, nous avons réduit la taille des messages : un catalogue plus compact, seulement les derniers échanges de l'historique, des réponses plus courtes.
▎
▎ Tout a été mesuré avec CodeCarbon, avant et après. »

🧠 Pour comprendre

- Pourquoi les tokens comptent. Un token est un morceau de mot, environ ¾ de mot en moyenne. Le modèle fait un calcul pour chaque token lu (entrée) et chaque token écrit (sortie). Plus de tokens, c'est plus de calcul, donc plus d'énergie et plus d'attente.
- D'où venaient les tokens avant. À chaque message, on envoyait le catalogue complet en JSON et tout l'historique, soit environ 1 225 tokens d'entrée par message. Maintenant :
  - une ligne par coffret (format_catalog) ;
  - seulement les coffrets compatibles avec les allergies ;
  - seulement les 6 derniers messages (HISTORY_MAX = 6).

  Résultat : 298 tokens d'entrée par message (−76 %).
- Côté réponses : la consigne demande 3 à 4 phrases, avec une limite de sécurité MAX_TOKENS = 300. La température est de 0,3 : moins de « créativité », des réponses plus stables. Les réponses passent de 748 à 180 caractères et de 205 à 27 tokens de sortie (−87 %).
- La FAQ (data/faq.json). Une question de 8 mots maximum qui contient un mot-clé (horaires, livraison…) reçoit la réponse fixe, qui renvoie vers le site. Une phrase plus longue est considérée comme une vraie demande et part au modèle.
- Le cache :
  - il ne concerne que le premier message d'une conversation, avec les mêmes allergènes cochés ;
  - il est gardé en mémoire seulement, jamais dans la base ;
  - il est vidé après 3 h, comme les sessions ;
  - il est limité à 200 entrées.
- Les modèles : llama3.2:3b (3 milliards de paramètres) et llama3.2:1b (1 milliard). Le 1b consomme environ 3 fois moins, mais se trompe plus, d'où le choix de le réserver à la politesse. Résultat : 9 appels au modèle au lieu de 15, et seulement 40 % au gros modèle au lieu de 100 %.
- Ce que mesure CodeCarbon : l'énergie consommée par le processeur, la carte graphique et la RAM pendant le test, multipliée par l'intensité carbone de l'électricité en France, environ 56 g de CO₂/kWh grâce au nucléaire. C'est pour ça que les valeurs sont en milligrammes.
  - Le CO₂ (82,9 → 22,9 mg) concerne la série de 15 messages, pas un message seul. L'énergie, elle, est donnée par message (0,099 → 0,027 Wh).
  - La limite à connaître : on mesure la machine locale seulement. Le réseau et la fabrication du matériel ne sont pas comptés. Il faut regarder l'écart relatif (−72 %), pas la valeur absolue.

---

Diapositive 6 : Fiabilité (≈ 1 min)

🎤 À dire

▎ « Au départ, quand quelque chose cassait, personne ne le savait : pas d'erreur dans les logs, et la page de santé répondait toujours "ok". Notre objectif était donc de rendre les erreurs visibles.
▎
▎ Chaque requête écrit maintenant des logs structurés avec un identifiant unique, ce qui permet de suivre une requête du début à la fin. Et ces logs ne contiennent jamais le texte des clients.
▎
▎ Les erreurs graves partent vers Sentry, un outil d'alerte. Nous l'avons configuré pour qu'il n'envoie aucune donnée personnelle, sur un serveur situé dans l'Union européenne.
▎
▎ Si le modèle ne répond pas, ChocoBot essaie le petit modèle en secours. Si les deux échouent, le client reçoit un message clair au lieu d'une erreur.
▎
▎ La page /health vérifie maintenant la base de données, le serveur de modèles et le catalogue, et répond 503 si l'un d'eux a un problème.
▎
▎ Enfin, le catalogue est vérifié au démarrage. Si un allergène manque dans la fiche d'un coffret, le bot refuse de conseiller plutôt que de donner un conseil dangereux. »

🧠 Pour comprendre

- Les logs structurés (observability.py).
  - Chaque événement est une ligne JSON : {"event": "llm_call", "model": "...", "latency_ms": ..., "request_id": "a1b2c3d4"}. Une machine peut les filtrer ou les compter, au lieu de texte libre.
  - Le request_id (8 caractères) est créé pour chaque requête HTTP, et renvoyé au client dans l'en-tête X-Request-ID.
  - Pour un message client, on ne journalise que sa longueur (message_length), jamais son contenu. Le script de test a vérifié 7 fichiers de logs : aucun texte de client.
- Ce qu'est Sentry. Un service qui reçoit les erreurs d'une application, les regroupe et envoie une alerte, par exemple par mail. Dans ChocoBot, tout log de niveau ERROR devient un événement Sentry. Les réglages, dans app.py :

| Réglage                       | Ce qu'il fait                                                                                  |
|-------------------------------|------------------------------------------------------------------------------------------------|
| send_default_pii=False        | n'envoie ni adresse IP, ni cookies, ni en-têtes personnels                                     |
| max_request_body_size="never" | n'envoie jamais le corps de la requête (messages, allergies)                                   |
| include_local_variables=False | n'envoie pas les variables du code (prompt, historique)                                        |
| traces_sample_rate=0          | pas de suivi de performance (sobriété)                                                         |
| DSN ingest.de.sentry.io       | données hébergées en Allemagne, donc dans l'UE : pas de transfert hors UE (chapitre V du RGPD) |
  Sans variable SENTRY_DSN, Sentry est simplement désactivé. Un point reste ouvert : désactiver aussi le stockage des IP dans les réglages du projet Sentry, côté site web.
- Le secours (call_model, llm.py) :
  - timeout de 30 s et max_retries=0. Avant, le client OpenAI réessayait tout seul en silence, ce qui pouvait faire attendre très longtemps.
  - On essaie le modèle choisi, puis llama3.2:1b. Un échec intermédiaire est journalisé en WARNING. Si tout échoue, c'est un ERROR, donc une alerte Sentry, et le client reçoit FALLBACK_REPLY.
  - Différence importante avec avant : l'ancien message d'erreur était enregistré dans l'historique comme si c'était une réponse du bot. Maintenant, la réponse de secours n'est jamais enregistrée.
- /health et le code 503. 503 veut dire « Service Unavailable ». C'est le code qu'attend un outil de supervision ou un répartiteur de charge pour savoir que le service est malade. Les vérifications :
  - un SELECT 1 sur SQLite ;
  - la présence des deux modèles dans Ollama ;
  - l'absence d'erreur dans le catalogue.

  Quand Ollama est arrêté, /health répond en 0,05 s, et la FAQ continue de fonctionner, puisqu'elle n'a pas besoin du modèle.
- La validation du catalogue (modèle Pydantic Coffret + contrôle de cohérence) :
  - avant, avec un JSON cassé : le serveur ne démarrait pas et affichait 75 lignes d'erreur incompréhensibles ;
  - avant, avec un allergène retiré de la fiche du coffret Beffroi : le bot le proposait à un allergique aux noisettes ;
  - maintenant : l'erreur est détectée et décrite précisément (ex. : « C01 (Coffret Beffroi) : le contenu mentionne « noisette » mais l'allergène « fruits à coque » n'est pas déclaré »). /health passe à 503, et le bot répond qu'il ne peut pas conseiller pour le moment.
- tests_auto.py relance toute la série de mesures (consommation, charge, pannes, catalogue) sur une copie du projet, sans toucher à la vraie base, et génère un rapport de comparaison avec la référence « avant ».

---

Diapositive 8 : Démonstration (≈ 4 min)

Avant de commencer : serveur lancé, Ollama allumé, un onglet sur localhost:8000, un onglet sur localhost:8000/health, un onglet Sentry, et la vidéo de secours prête.

Étape: 1
Ce que tu fais: Accepter la notice
🎤 Ce que tu dis: « Avant toute chose,
l'utilisateur est informé : la notice
explique quelles données sont traitées et
combien de temps elles sont gardées. Et on
voit l'avertissement : c'est une IA, ses
réponses peuvent être fausses. »
────────────────────────────────────────
Étape: 2
Ce que tu fais: Écrire « Quels sont vos
horaires ? »
🎤 Ce que tu dis: « Réponse immédiate : c'est
une réponse fixe, le modèle n'a pas été
appelé. Zéro token consommé. »
────────────────────────────────────────
Étape: 3
Ce que tu fais: Cocher « Fruits à coque », puis
écrire « Je cherche un coffret  pour 30 euros
 pour offrir »
🎤 Ce que tu dis: « J'ai coché une allergie.
Avant même que l'IA ne lise la question, le
code a retiré du catalogue tous les coffrets
avec des fruits à coque. L'IA ne peut donc
pas proposer un coffret dangereux : elle ne
le voit pas. »
────────────────────────────────────────
Étape: 4
Ce que tu fais: Ouvrir /confidentialite (15 s)
🎤 Ce que tu dis: « La notice complète,
accessible à tout moment. »
────────────────────────────────────────
Étape: 5
Ce que tu fais: Arrêter Ollama (selon votre
installation : sudo systemctl  stop ollama ou
 docker stop  <conteneur>), puis écrire un
message
🎤 Ce que tu dis: « Je simule une panne. Le
client reçoit un message clair au lieu d'une
erreur. »
────────────────────────────────────────
Étape: 6
Ce que tu fais: Rafraîchir /health
🎤 Ce que tu dis: « La page de santé passe à
503 et indique exactement ce qui ne va pas :
ici, le serveur de modèles. »
────────────────────────────────────────
Étape: 7
Ce que tu fais: Montrer Sentry
🎤 Ce que tu dis: « Et l'équipe est alertée. On
voit l'erreur, mais aucun message de client,
aucune allergie, aucune IP. »
────────────────────────────────────────
Étape: 8
Ce que tu fais: Écrire « Quels sont vos
horaires ? » pendant la panne
🎤 Ce que tu dis: « Même en panne, les
questions fréquentes fonctionnent toujours. »
────────────────────────────────────────
Étape: 9
Ce que tu fais: Relancer Ollama, puis effacer
la session
🎤 Ce que tu dis: « Enfin, l'utilisateur peut
effacer sa conversation : c'est son droit à
l'effacement (article 17 du RGPD). »

🧠 Pour comprendre

- L'étape 3 est le cœur de la démo. La sécurité ne repose pas sur l'IA, qui peut se tromper, mais sur le code, qui filtre avant. C'est pour ça qu'on passe de 12/18 à 0/18 recommandations dangereuses.
- Si le bot répond « tous nos coffrets contiennent des noisettes » pendant la démo, c'est le problème des refus abusifs (E7). Dis-le calmement : « C'est un des problèmes qu'il nous reste, nous en parlons juste après. » Ça montre que vous connaissez vos limites.
- Répète la démo au moins une fois avant, surtout l'arrêt d'Ollama et la vérification que l'alerte Sentry arrive bien. Sentry peut mettre quelques secondes à afficher l'erreur.

---

Diapositive 10 : Ce que nous en retenons (≈ 45 s)

🎤 À dire

▎ « Pour conclure, nous retenons trois choses.
▎
▎ D'abord, mesurer avant de corriger. Sans nos mesures de départ, nous ne pourrions pas affirmer que la consommation a baissé de 72 %. Et nous avons automatisé ces mesures pour que la prochaine version soit testée en une commande.
▎
▎ Ensuite, la conformité et la sobriété vont dans le même sens. Envoyer moins de données au modèle, c'est à la fois mieux pour la vie privée, moins d'énergie et des réponses plus rapides. Le RGPD parle de minimisation : c'est aussi un principe de sobriété.
▎
▎ Enfin, une panne invisible est plus dangereuse qu'une panne visible. Un bot qui se trompe sans que personne ne le sache, c'est ce qu'il y avait au départ. Aujourd'hui, chaque erreur est journalisée, signalée, et le client est prévenu.
▎
▎ Merci, nous sommes prêtes pour vos questions. »

---

Questions probables du jury

- « Pourquoi pas tout sur le petit modèle, si c'est plus sobre ? » Parce qu'il se trompe davantage. Pour un conseil qui touche aux allergies, une erreur peut rendre quelqu'un malade. On économise là où le risque est nul.
- « Pourquoi le test de charge simultanée est moins bon qu'avant ? » Avec 5 clients au même instant, la base SQLite utilise une seule connexion partagée, et certaines requêtes échouent : 2 clients sur 5 terminent au lieu de 3. Les requêtes vont pourtant beaucoup plus vite (17,6 s au lieu de 101 s), et avec des clients échelonnés, 5 sur 5 terminent. La correction prévue est une connexion par requête.
- « Les mg de CO₂, c'est négligeable, non ? » Pour un test, oui. Mais multiplié par des milliers de clients par jour, et sur un réseau électrique plus carboné qu'en France, l'écart de −72 % devient significatif. Et la baisse de latence améliore aussi l'expérience client.
- « Le consentement pour les allergies est-il valable ? » Les cases sont facultatives, et le bot fonctionne sans. Comme amélioration, on pourrait sortir la mention des allergènes de la case d'acceptation obligatoire, pour un consentement explicite bien séparé.