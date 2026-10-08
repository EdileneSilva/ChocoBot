# Rapport des tests automatiques — apres

Date : 2026-10-08 16:10 · Code : `2e856f2-dirty` · Référence : mesures/avant/resultats.json

Généré par `tests_auto.py`. Les recommandations dangereuses comptées automatiquement doivent être vérifiées à la main (réponses listées en fin de `resultats.json`).

## Consommation (test 1, moyenne des exécutions)

| Indicateur | Référence | Actuel | Écart |
|---|---|---|---|
| Appels au modèle (15 messages) | 15 | 9 | -40 % |
| Part du gros modèle | 100.0 % | 40.0 % | -60 % |
| Tokens d'entrée / message | 1225.3 | 297.8 | -76 % |
| Tokens de sortie / message | 205.4 | 27.2 | -87 % |
| Tokens totaux (15 messages) | 21461 | 4874 | -77 % |
| Latence moyenne | 5.51 s | 2.31 s | -58 % |
| Latence p95 | 8.24 s | 6.7 s | -19 % |
| Longueur moyenne des réponses | 748 car. | 180 car. | -76 % |
| Énergie / message | 0.0986 Wh | 0.0273 Wh | -72 % |
| CO₂e (15 messages) | 82.9 mg | 22.9 mg | -72 % |
| Reco. dangereuses, question allergie (auto) | ['1/3', '2/3', '3/3'] | ['0/3', '0/3', '0/3'] |  |
| Reco. dangereuses, question enfants (auto) | — | ['0/3', '0/3', '0/3'] |  |

## De bout en bout et charge (tests 2 et 3)

| Indicateur | Référence | Actuel | Écart |
|---|---|---|---|
| load_test.py 2 : durée | 55.1 s | 27.4 s | -50 % |
| Pic simultané (3a) : clients terminés / 5 | 3 | 2 | -33 % |
| Pic simultané (3a) : erreurs HTTP 500 | 2 | 3 | +50 % |
| Pic simultané (3a) : durée totale | 101.4 s | 17.6 s | -83 % |
| Pic simultané (3a) : temps par message vu par un client | 20.3 s | 3.5 s | -83 % |
| Pic échelonné (3b) : clients terminés / 5 | 5 | 5 | +0 % |
| Pic échelonné (3b) : erreurs HTTP 500 | 0 | 0 |  |
| Pic échelonné (3b) : durée totale | 158.1 s | 29.7 s | -81 % |
| Pic échelonné (3b) : temps par message vu par un client | 29.2 s | 5.3 s | -82 % |

## Pannes (tests 4 et 4b)

| Indicateur | Référence | Actuel |
|---|---|---|
| Panne API : erreur journalisée (ERROR) | 0 | 2 |
| Panne API : cause visible dans le log | non | oui |
| Panne API : réponses d'erreur enregistrées comme réponses | 3 | 0 |
| Panne API : réponse reçue par le client | Désolé, une erreur est survenue. Réessayez plus tard. | Désolé, je ne peux pas répondre pour le moment. Vous pouvez réessayer dans quelques instants ou consulter nos coffrets sur notre site. |
| Serveur de modèles injoignable : `/health` | 200 | 503 |
| Serveur de modèles injoignable : durée de la réponse | — | 0.049 s |
| Serveur de modèles injoignable : FAQ disponible | — | oui |

## Catalogue corrompu (tests 5a et 5b)

| Indicateur | Référence | Actuel |
|---|---|---|
| 5a JSON invalide : serveur démarre | non | oui |
| 5a JSON invalide : erreur détectée et signalée | non | oui |
| 5a JSON invalide : `/health` | — | 503 |
| 5b allergène retiré : erreur détectée | non | oui |
| 5b allergène retiré : Beffroi proposé à un allergique | oui | non |
| 5b allergène retiré : `/health` | 200 | 503 |

Messages 5a : ["catalog.json : JSON invalide ligne 3, colonne 3 : Expecting ',' delimiter (l'erreur peut se trouver à la fin de la ligne précédente)"]

Messages 5b : ["C01 (Coffret Beffroi) : le contenu mentionne « noisette » mais l'allergène « fruits a coque » n'est pas déclaré"]

## Confidentialité des logs

7 logs de serveur vérifiés ; textes de clients retrouvés : aucun.
