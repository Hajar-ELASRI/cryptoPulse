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

## Suite : reprise des imports longs

Le chargeur a été renforcé pour les six archives BTCUSDT/ETHUSDT de juillet à septembre 2026, disponibles lors de la vérification HTTP : 3 691 117 046 octets de ZIP au total, environ 36,25 Go de CSV. L'espace libre du disque hôte mesuré avant lancement dépassait 134 Go; le chargeur conserve une réserve configurable de 10 Gio et ne matérialise pas le CSV entier sur disque.

L'import conserve désormais les téléchargements interrompus et reprend via HTTP Range. Les lots Mongo sont enregistrés dans `history_imports`; les écritures par insertion groupée conservent les transactions existantes grâce à l'index unique. Les prix, dates et champs de `trades_history` ne changent pas.

**14 tests ont réussi dans le conteneur avec MongoDB**, dont sept nouveaux contrôles : coupure HTTP suivie d'une reprise partielle, serveur ignorant Range, passage d'un échantillon à un import complet, interruption entre insertion et checkpoint, suppression d'une ligne après checkpoint, changement du contenu de l'archive et refus d'ignorer une violation d'un autre index unique. Ces tests utilisent une archive locale fabriquée pour les scénarios et des bases Mongo temporaires distinctes; ils ne valent pas validation de la série BTC/ETH réelle.

Le premier essai réel, utilisant l'ancien téléchargeur, s'est arrêté après une coupure réseau à environ 106 Mo du premier ZIP. **Ce premier lancement ne constitue pas un import terminé.** Consulter les logs du conteneur nommé et les six checkpoints avant d'annoncer la fin de la série.

### Reprise du 23 octobre 2026

Le moteur Docker/WSL ne répondait plus (erreur 500); il a été remis en service sans suppression des volumes. La vérification d'ingestion a ensuite retourné `ok: true` à nouveau.

Les **six ZIP ont été téléchargés et contrôlés** avec `scripts.history_download` sur Windows pendant la remise en service, soit **3 691 117 046 octets**. L'inventaire local est enregistré sous `data/history/download-inventory.json` et reste exclu de Git.

La nouvelle version de l'importeur tourne dans `cryptopulse-history-btc-eth`, avec les deux symboles et les trois mois explicitement fixés. La politique `on-failure:3` a été appliquée et vérifiée. Un contrôle a confirmé **2 220 000 nouvelles lignes BTCUSDT** traitées dans le premier mois. La première date est `2026-07-01T00:00:00.054Z`, et la dernière de ce checkpoint est `2026-07-01T13:59:10.119Z`; prix et quantités restent des chaînes. Un contrôle précédent par `history_status --verify` avait confirmé l'égalité du compte stocké et du checkpoint à 1 144 000 lignes.

**La série complète reste en cours.** Les points de reprise `history_imports` et `scripts.history_status --verify --require-complete` fournissent l'état à jour; les nombres ci-dessus sont des observations datées, pas un compte final des six archives.
