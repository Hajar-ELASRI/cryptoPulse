# CryptoPulse — contexte général du projet

## 1. Résumé

CryptoPulse est un prototype Big Data qui collecte des transactions de cryptomonnaies et des informations de marché, les transforme en indicateurs utiles et les présente dans un tableau de bord. Le but n'est pas de conserver uniquement des données brutes : chaque événement doit être contrôlé, normalisé, enrichi et agrégé avant d'être exploité.

**Question de démonstration :** comment transformer les transactions, actualités et publications sociales disponibles en indicateurs explicables (volume, variation, anomalies, sentiment) et permettre à un utilisateur de les consulter et de rejouer une période ? Le projet est pédagogique : une corrélation entre sentiment et prix n'établit pas de causalité et le sentiment automatique n'est pas un conseil financier.

## 2. Équipe et répartition

Le groupe comporte quatre membres : Ali, Mossab, Hajar et Mohammed. Les tâches individuelles sont décrites dans les briefs autonomes du dossier [`team`](team/).

| Membre | Domaine principal | Situation |
|---|---|---|
| Hajar | Ingestion et infrastructure | Base déjà présente dans la branche actuelle; terminer la validation et les interfaces avec Spark. |
| Ali | Traitements Big Data Spark | À développer. |
| Mossab | API Spring Boot | À développer. |
| Mohammed | Tableau de bord React et préparation de la démo | À développer. |

Les trois chantiers hors ingestion ont été distribués au hasard entre Ali, Mossab et Mohammed. Les tâches de coordination et d'intégration sont communes.

## 3. Dépôt et état connu

- Dépôt distant : [Hajar-ELASRI/cryptoPulse](https://github.com/Hajar-ELASRI/cryptoPulse).
- Branche de travail de la base existante : `codex/person-a-ingestion`.
- La base comprend Docker Compose avec Kafka, MongoDB et Spark, les collecteurs Binance/RSS/Reddit, l'import historique Binance, un service de sentiment VADER, des tests unitaires et la documentation initiale.
- Le contrat initial est [`contracts.md`](contracts.md); le plan de travail antérieur est [`plan-travail.md`](plan-travail.md).
- Validation du 22 octobre 2026 : les sept tests d'ingestion passent; Kafka, MongoDB, le master/worker Spark et les flux réels Binance/RSS/sentiment ont été vérifiés. Voir le [rapport d'ingestion](validation-ingestion.md) pour le périmètre exact et les résultats historiques. Les jobs métier Spark, l'API et le dashboard restent à construire; le projet applicatif complet n'est pas encore validé.
- À l'inspection de départ de ce document, aucune branche ni contribution des autres membres n'était présente sur le dépôt distant. Vérifier l'état GitHub avant de commencer.
- Suite au 23 octobre 2026 : l'import BTCUSDT/ETHUSDT de juillet à septembre 2026 est lancé avec reprise et suivi par archive. Le [rapport](validation-ingestion.md) distingue les téléchargements, les lignes déjà stockées et l'import complet encore en cours.

## 4. Architecture visée

```text
Binance WebSocket ─┐
RSS actualités ─────┼─> collecteurs Python ─> Kafka ─> Spark Structured Streaming
Reddit (optionnel) ┘                                  │
Historique Binance ─> MongoDB trades_history ─────────┤
Service sentiment ───────────────> Kafka              │
                                                      v
                                              MongoDB (Silver/Gold)
                                                      │
                                              API Spring Boot
                                                      │
                                              React dashboard
```

Kafka est le bus d'événements. MongoDB conserve les données historiques et les résultats consultables. Spark réalise les transformations Big Data. Spring Boot expose les lectures au client. React affiche l'état du marché, les alertes, le sentiment, l'analytique et le replay.

## 5. Données entrantes

### Transactions Binance

Le collecteur publie dans `crypto-trades`. Le contrat actuel contient `event_id`, `source`, `symbol`, `trade_id`, `price`, `quantity`, `event_time`, `ingested_at` et `is_buyer_maker`. Prix et quantités arrivent sous forme de chaînes décimales afin de préserver la précision. Exemple complet dans [`contracts.md`](contracts.md).

### Actualités RSS

Le collecteur normalise les articles dans `crypto-news` : identifiant stable, titre, résumé, URL, date de publication/événement et date d'ingestion. Les champs exacts doivent rester synchronisés avec le contrat.

### Réseaux sociaux (facultatif selon accès)

Le collecteur Reddit lit des communautés crypto et publie dans `crypto-social`. Il exige des identifiants OAuth valides dans un fichier `.env` local. Ne jamais committer ces secrets. Le projet doit rester démontrable sans Reddit si l'accès API n'est pas disponible.

### Historique et sentiment

Le chargeur Binance remplit `trades_history` dans MongoDB et déduplique par symbole et identifiant de trade. Le service VADER publie des scores dans `crypto-sentiment`. VADER est un point de départ en anglais; ses résultats sur l'argot crypto doivent être évalués et ses limites rapportées.

## 6. Valeur ajoutée : transformations à réaliser

Le flux doit démontrer des étapes mesurables entre les données brutes et les résultats destinés à l'application.

### Bronze — entrée conservée

Lire les messages Kafka et garder la possibilité de retrouver la source et l'identifiant d'événement. Les données brutes facilitent le diagnostic et la comparaison avant/après.

### Silver — événements propres et enrichis

1. Parser avec un schéma explicite, rejeter ou mettre de côté les messages invalides et documenter le motif.
2. Convertir `event_time` en timestamp UTC et `price`/`quantity` en `DecimalType`.
3. Dédupliquer par `event_id` avec watermark pour le streaming; traiter les retards selon une durée décidée par l'équipe.
4. Valider les règles de base : champs obligatoires, prix/quantité positifs, symbole connu, dates plausibles.
5. Calculer `quote_volume = price × quantity` (montant exprimé dans la devise de cotation, par exemple USDT).
6. Écrire les événements nettoyés dans `trades` et les documents éditoriaux propres dans `news` / `social_posts`.

### Gold — agrégats, détection et contexte

Produire une ligne par symbole et fenêtre d'une minute dans `indicators`, avec au minimum début/fin de fenêtre, nombre de trades, volume de base, volume coté, prix min/max et prix moyen ou dernier prix.

Calculer la variation entre fenêtres : `100 × (prix_courant - prix_précédent) / prix_précédent`. Définir précisément le prix utilisé (moyen ou clôture) et le documenter.

Créer des alertes explicables dans `alerts` :

- pic de volume : volume de la minute comparé à la moyenne des 20 minutes précédentes (seuil initial suggéré : 2×; période de chauffe avant activation);
- mouvement de prix : variation absolue dépassant un seuil décidé après inspection;
- grande transaction : `quote_volume` d'un trade dépassant un seuil configurable.

Chaque alerte inclut le symbole, type, heure, valeur mesurée, seuil et texte de raison. Les seuils de démonstration sont des paramètres configurables et doivent être présentés comme tels, pas comme des valeurs de marché universelles.

Associer les sentiments/articles aux symboles quand c'est possible, calculer des agrégats temporels et afficher ce contexte près des indicateurs. L'interface et le rapport doivent parler de corrélation observée, jamais de causalité prouvée.

### Replay

Permettre de retraiter une période depuis `trades_history` en réutilisant la logique des fenêtres/alertes. Éviter de mélanger les résultats du replay aux données live : définir un identifiant de session ou une stratégie de nettoyage, et rendre l'opération reproductible.

## 7. Collections MongoDB attendues

- `trades_history` : source historique importée, index unique `(symbol, trade_id)` et accès par `(symbol, event_time)`.
- `trades` : transactions validées et enrichies avec `quote_volume`.
- `news`, `social_posts`, `sentiment` : événements éditoriaux nettoyés et enrichis.
- `indicators` : agrégats par symbole/fenêtre.
- `alerts` : anomalies avec mesures et seuils explicables.

Le schéma des sorties doit être confirmé par toute l'équipe et ajouté à [`contracts.md`](contracts.md) avant l'intégration API. Prévoir clés d'idempotence/upsert et index utiles aux filtres temporels.

## 8. Contrats et interfaces

- Kafka : noms de topics et JSON dans [`contracts.md`](contracts.md). Garder `event_id` stable, les heures en UTC ISO-8601 et les nombres décimaux précis.
- MongoDB : Ali et Hajar valident ensemble les champs des collections Silver/Gold; Mossab et Mohammed consomment ces champs sans les réinterpréter.
- REST : Mossab documente les routes et exemples JSON dans `docs/contracts.md` ou un fichier API dédié. Les routes prévues sont `/api/live`, `/api/alerts`, `/api/sentiment`, `/api/replay` et `/api/analytics`.
- Les évolutions d'un champ/type doivent être annoncées et mises à jour dans le contrat avant que les consommateurs changent leur code.

## 9. Organisation et méthode de travail

1. Chaque membre lit ce contexte et son brief individuel.
2. Faire un kickoff court : confirmer les contrats, seuils de démonstration, disponibilité Docker et accès Reddit; attribuer un responsable d'intégration.
3. Créer/mettre à jour les branches de l'équipe selon le dépôt réel. Travailler sur branches `feature/<sujet>`, ouvrir des PR vers la branche d'intégration convenue et demander une revue croisée. Ne pas supposer que `main`/`develop` existent sans vérifier.
4. Développer en parallèle sur des exemples conformes au contrat; le frontend peut démarrer sur des réponses mockées documentées.
5. Intégrer dans l'ordre : ingestion Kafka → Spark vers Mongo → API → interface; remplacer les mocks et vérifier un même événement de bout en bout.
6. Réaliser une démo reproductible avec un scénario normal et un scénario synthétique déclenchant une alerte; garder une solution de secours locale si une source externe est indisponible.
7. Dans les PR, décrire fichiers touchés, commandes de lancement, captures/résultats utiles et problèmes connus. Ne committer aucun secret ni donnée personnelle.

## 10. Jalons et critères d'acceptation

### Jalon 1 — contrats et démarrage

- Équipe d'accord sur champs, types, fuseaux horaires, noms de collections et format d'alertes.
- Compose se lance sur au moins une machine de l'équipe; services et commandes sont documentés.

### Jalon 2 — pipeline de transformation

- Un événement d'exemple valide produit un document Silver avec timestamp et types normalisés, déduplication et `quote_volume`.
- Les entrées invalides/duplicatas ont un comportement documenté.
- Une série de trades produit des indicateurs minute vérifiables à la main.

### Jalon 3 — application intégrée

- L'API retourne les collections Gold avec filtres cohérents; le dashboard les montre.
- Les alertes exposent la raison, la valeur et le seuil.
- Le sentiment et le replay affichent leurs limites et leur période.

### Jalon 4 — présentation

- Démo du flux complet, transformation avant/après, indicateur calculé, alerte déclenchée, vue de sentiment et replay historique.
- Rapport expliquant formules, seuils, mesures de latence/débit si disponibles, limites et plan de secours.

## 11. Démarrage local connu

Voir le [`README.md`](../README.md) pour les commandes à jour. La procédure existante utilise `docker compose up --build -d`; l'historique s'importe avec le profil `history`. Reddit est optionnel et dépend de credentials. Vérifier les logs et la configuration Compose avant de conclure que le pipeline fonctionne. Garder `.env` hors Git.

## 12. Glossaire

- **Topic** : canal Kafka où sont publiés les événements.
- **Watermark** : limite de retard acceptée par Spark pour gérer l'état et les doublons en streaming.
- **Silver** : données nettoyées, typées, validées et enrichies.
- **Gold** : agrégats et indicateurs prêts à servir les usages métier.
- **Replay** : retraitement d'un historique avec les mêmes règles que le flux.
- **Valeur cotée / quote volume** : prix multiplié par quantité, exprimé dans la devise de cotation.
