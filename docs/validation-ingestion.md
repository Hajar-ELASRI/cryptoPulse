# Validation de la partie Hajar — 22 octobre 2026

## Périmètre et résultat

La partie ingestion et l'infrastructure locale ont été exécutées sur Docker Desktop Linux. Ce contrôle couvre les sources réelles Binance/RSS, Kafka, MongoDB, le cluster Spark démarré et la production de sentiment VADER. Les traitements métier Spark d'Ali, l'API de Mossab et le dashboard de Mohammed ne sont pas encore implémentés dans cette branche.

Configuration finale contrôlée : Kafka `4.3.1`, MongoDB `8.0`, Spark `3.5.9-scala2.12-java17-python3-ubuntu`. Les substitutions locales d'images utilisées pendant le diagnostic ont été retirées du `.env` après disponibilité des images finales.

## Vérifications effectuées

- `python -m unittest discover -s tests -v` : **7 tests réussis** (normalisation, dates, identifiants, mois historiques, données non finies/non positives, détection des symboles avec ponctuation).
- `docker compose config --quiet` : configuration valide.
- Démarrage de la pile : Kafka/MongoDB sains, initialisations terminées avec le code 0, un worker Spark enregistré auprès du master.
- Contrôle opérationnel par le profil `verify` : résultat JSON `ok: true`, constaté à **2026-10-22T13:52:04Z**.
- Quatre topics créés : `crypto-trades`, `crypto-news`, `crypto-social`, `crypto-sentiment`; chacun possède 3 partitions.
- Trois événements par flux obligatoire ont passé les contrôles du script : transactions Binance, articles RSS et résultats de sentiment. Ce sont des échantillons effectivement lus dans Kafka, pas des données simulées.
- Les logs des sources indiquaient une connexion WebSocket Binance réussie et la lecture de 25 articles CoinDesk et 30 articles Cointelegraph lors du démarrage observé. Ces nombres dépendent du contenu des flux au moment de l'exécution.
- MongoDB : sept collections attendues présentes et index historique unique `(symbol, trade_id)` confirmé.

Le script vérifie la forme des échantillons disponibles dans Kafka et leurs métadonnées. Il ne prouve pas la validité de tous les événements passés, la fraîcheur des sources à un autre instant, la qualité prédictive du sentiment ou la justesse des futurs agrégats Spark.

## Historique réel importé

Archive : `BNBBTC-trades-2025-01.zip` depuis Binance Public Data; taille compressée de 16 268 484 octets. Le symbole BNBBTC a été choisi pour intégrer un mois complet avec un volume plus limité que BTCUSDT/ETHUSDT.

1. Import limité aux 1 000 premières transactions : **1 000 nouvelles lignes**.
2. Relance du même import limité : **0 nouvelle ligne**, compte inchangé à 1 000 et 0 groupe de doublons dans l'échantillon.
3. Import de la même archive entière : **1 381 513 nouvelles lignes**, en complément des 1 000 déjà présentes.
4. Compte final : **1 382 513 documents**, égal aux **1 382 513 lignes de transactions du CSV**.
5. Première date : `2025-01-01T00:00:06.739Z`.
6. Dernière date : `2025-01-31T23:59:49.438Z`.
7. Documents historiques BNBBTC dont `event_time` n'est pas une date BSON : **0**. Index unique vérifié sur l'ensemble de la collection.

Le contrôle d'idempotence a été effectué sur l'échantillon de 1 000 lignes. L'import complet n'a pas été rejoué une seconde fois; le mécanisme d'upsert et l'index unique restent les mêmes.

L'archive/cache et les volumes Mongo sont locaux, exclus de Git. Chaque membre doit importer les données sur sa propre machine s'il en a besoin. Le chargement final de plusieurs mois BTCUSDT/ETHUSDT reste configurable et à dimensionner avec l'équipe; il n'est pas couvert par ce compte BNBBTC. La devise de cotation de BNBBTC est BTC, celle de BTCUSDT est USDT : le replay doit conserver le symbole et l'unité de volume associés.

## Correctifs réalisés pendant la validation

- Le broker ne pouvait pas écrire dans le volume neuf monté sous `/tmp/kraft-combined-logs`. Un service d'initialisation fixe le propriétaire du répertoire avant son démarrage.
- Les images Kafka et Spark sont paramétrables; la configuration par défaut finale correspond aux versions contrôlées. Le master annonce un nom de service stable; le worker utilise 2 cœurs et 1 Go.
- Ajout du profil `verify` et de son script de vérification sans validation d'offsets Kafka.
- L'import historique accepte un mois fixé et une limite de lignes par archive pour rendre les essais reproductibles.
- Validation décimale des transactions renforcée; détection des symboles de sentiment améliorée pour la ponctuation et les cashtags.
- `.dockerignore` empêche l'envoi de `.env`, de Git et des données dans le contexte de build; `.gitattributes` conserve les scripts shell en LF.

## Éléments restant à coordonner

- Reddit : profil désactivé, credentials OAuth absents; aucun événement social réel ni authentification Reddit validé ici.
- Ali : confirmer les schémas Mongo de sortie, construire les jobs Silver/Gold et le replay. Le worker disponible ne constitue pas encore un pipeline métier Spark.
- Mossab et Mohammed : construire puis brancher API et frontend sur les sorties transformées.
- Équipe : décider de la branche d'intégration et du volume/symboles d'historique retenus pour la soutenance. Au démarrage de ce travail, la branche distante partagée était `codex/person-a-ingestion`.

Les commandes de lancement, de diagnostic et d'import sont dans le [guide d'exploitation](ingestion-operations.md).
