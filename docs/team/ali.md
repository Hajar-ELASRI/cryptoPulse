# Brief de travail — Ali

## Mission attribuée

Développer le pipeline de transformations Big Data avec Spark Structured Streaming. Cette répartition parmi les trois chantiers encore libres (Spark, API, frontend) a été tirée au hasard; Hajar conserve l'ingestion déjà commencée.

## Résultat attendu

À partir des messages bruts des topics Kafka, produire des documents propres et enrichis dans MongoDB, puis calculer des indicateurs par minute et des alertes explicables. C'est le chantier qui matérialise la transformation demandée par l'enseignante.

## À lire avant de coder

- [`Contexte général`](../project-context.md)
- [`Contrats Kafka et MongoDB`](../contracts.md)
- [`Plan de travail d'origine`](../plan-travail.md)

Confirmer les champs et schémas de sortie avec Hajar (productrice/infra), Mossab (API) et Mohammed (dashboard) avant de figer l'interface MongoDB.

## Tâches

1. Ajouter un job Spark, son schéma explicite et les paramètres de connexion Kafka/Mongo via variables d'environnement.
2. Lire `crypto-trades`; gérer messages invalides avec logs ou collection/quarantaine documentée.
3. Normaliser UTC, convertir prix/quantité en décimaux, valider les valeurs et dédupliquer par `event_id` avec watermark.
4. Calculer `quote_volume = price × quantity`; écrire les événements Silver dans `trades` de façon idempotente.
5. Calculer, par symbole et minute, compte de trades, volumes base/coté, min/max et prix moyen ou clôture choisi. Ajouter la variation vs fenêtre précédente.
6. Implémenter les alertes configurables de pic de volume, mouvement important et grande transaction. Chaque alerte doit inclure la valeur observée, le seuil, l'heure et une raison lisible.
7. Écrire dans `indicators` et `alerts`, créer/documenter index et checkpoints afin que le redémarrage ne double pas les résultats.
8. Ajouter le replay de `trades_history` avec la même logique; isoler les sorties de replay des sorties live.
9. Écrire les contrats définitifs, exemples de calcul à la main, paramètres et limites dans la documentation.

## Handoff / dépendances

- Hajar fournit les topics et événements conformes à `docs/contracts.md`; lui signaler immédiatement toute divergence de payload.
- Mossab consomme `trades`, `indicators`, `alerts`, `sentiment`; convenir ensemble des noms, dates, identifiants et pagination/filtrage.
- Mohammed consomme les mêmes sorties via l'API; transmettre des documents JSON d'exemple et explication des seuils.
- Le contrat partagé est la source de vérité. Ne pas changer le schéma silencieusement.

## Définition de terminé

- Exemple connu validé du brut jusqu'à Mongo avec tous les types corrects et `quote_volume` exact.
- Doublon ignoré, valeur invalide gérée, événement retardé comportement documenté.
- Exemple de plusieurs minutes reproduit les agrégats et la variation calculés manuellement.
- Scénario synthétique déclenche une alerte attendue avec cause et seuil affichés.
- Streaming redémarrable avec checkpoint/idempotence; replay documenté et reproductible.
- README/contrat mis à jour et PR revue par un autre membre.

## Hors périmètre principal

Ne pas implémenter l'API Spring Boot ni l'interface React; fournir à leurs propriétaires les contrats et exemples dont ils ont besoin. Les réglages d'infrastructure et collecteurs appartiennent principalement à Hajar.
