# CryptoPulse — ingestion and local infrastructure

Infrastructure and ingestion for the Big Data project. Hajar owns Binance Spot transactions, RSS news, optional Reddit posts, historical Binance trades, and sentiment enrichment. Ali owns Spark transformations, Mossab the Spring Boot API, and Mohammed the React dashboard.

Start with the [complete project context](docs/project-context.md), then open the [team member briefs](docs/team/README.md). The original work plan and transformation notes are in [docs/plan-travail.md](docs/plan-travail.md).

Work happens on branches named by the [branch convention](docs/branching.md) and merges into `main`. The Spark pipeline is described in [docs/spark-operations.md](docs/spark-operations.md). See the [ingestion runbook](docs/ingestion-operations.md) for operational checks, bounded history imports and connection details, and the [validation report](docs/validation-ingestion.md) for the verified state.

## Start

1. Install Docker Desktop and start its Linux engine.
2. Copy `.env.example` to `.env`. The defaults start Binance, RSS, Kafka, MongoDB, Spark, and sentiment. Set Reddit OAuth credentials and a real user agent before enabling Reddit.
3. Run `docker compose up --build -d`.
4. Check `docker compose ps` and `docker compose logs -f binance-collector rss-collector sentiment`.
5. Inspect events with:

   ```sh
   docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:19092 --topic crypto-trades --from-beginning --max-messages 3
   docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:19092 --topic crypto-news --from-beginning --max-messages 3
   docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:19092 --topic crypto-sentiment --from-beginning --max-messages 3
   ```

The first run downloads large Docker images. Kafka is available to host programs at `localhost:9092` and to other containers at `kafka:19092`. MongoDB is available at `localhost:27017` and `mongo:27017`; Spark master UI is at `http://localhost:8080` and its internal URL is `spark://spark-master:7077`.

## Reddit

Reddit requires approved API access and OAuth client credentials. Enter `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` and a real `REDDIT_USER_AGENT` in `.env`, then run `docker compose --profile reddit up --build -d`. The service reads `r/CryptoCurrency` and `r/Bitcoin` through `oauth.reddit.com`, honours `429 Retry-After`, and logs authentication errors. Do not commit `.env`.

After enabling Reddit, inspect `crypto-social` with the same Kafka console consumer command used above, changing `--topic` to `crypto-social`.

## Historical import

Set `HISTORY_MONTHS=3` or `6` and `HISTORY_SYMBOLS=BTCUSDT,ETHUSDT`, then run `docker compose --profile history run --rm historical-loader`. This imports the most recent **completed** calendar months. Interrupted downloads resume from `.part` files. MongoDB writes use bulk insertion and the unique trade index to retain existing records; committed batches are checkpointed in `history_imports`. See the [runbook](docs/ingestion-operations.md) for recovery and background imports. The volume can be large, so try `HISTORY_MONTHS=1` first. Binance Spot CSV timestamps from 2025 onward are microseconds; the loader accepts both microseconds and older milliseconds.

Verify the import with `docker compose exec mongo mongosh --quiet crypto_pulse --eval 'db.trades_history.countDocuments({})'`.

## Integration contract

Read [docs/contracts.md](docs/contracts.md) with Person B before building the Spark jobs. In particular, prices and quantities are sent as decimal strings, and the sentiment service writes to `crypto-sentiment` for B to consume.

The sentiment classifier uses the English VADER model. It produces a useful baseline for English titles and posts; assess its output on crypto slang before presenting sentiment as a reliable market signal.

## Local checks

Run `docker compose --profile verify run --build --rm ingestion-check` to verify MongoDB, a registered Spark worker, four Kafka topics and real trade/news/sentiment samples. The command reads without committing consumer offsets and exits nonzero if a required stream is missing.

Run `python -m unittest discover -s tests -v` for local checks and `docker compose config --quiet` for Compose syntax. Parser checks use the standard library; HTTP recovery checks require `requests`, and MongoDB recovery checks run when `MONGO_TEST_URI` is set. The [runbook](docs/ingestion-operations.md) includes the container command that runs the full suite against disposable MongoDB databases.

## Source documentation

- [Binance public data](https://github.com/binance/binance-public-data)
- [Apache Kafka single-node Docker Compose example](https://github.com/apache/kafka/blob/trunk/docker/examples/docker-compose-files/single-node/plaintext/docker-compose.yml)
- [Reddit API reference](https://www.reddit.com/dev/api/)
