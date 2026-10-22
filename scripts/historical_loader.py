"""Download monthly Binance Spot trades and upsert them in MongoDB in batches."""

import csv
import io
import logging
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from zipfile import BadZipFile, ZipFile

from collectors.common import iso_from_epoch


LOG = logging.getLogger(__name__)
BASE_URL = "https://data.binance.vision/data/spot/monthly/trades"


def previous_months(count: int, today: date | None = None) -> list[str]:
    current = today or date.today()
    year, month = current.year, current.month
    output = []
    for _ in range(count):
        month -= 1
        if month == 0:
            year, month = year - 1, 12
        output.append(f"{year:04d}-{month:02d}")
    return list(reversed(output))


def parse_trade_row(row: list[str], symbol: str) -> dict:
    if len(row) < 7:
        raise ValueError("Expected 7 Binance Spot trades CSV columns")
    trade_id, price, quantity, quote_quantity, raw_time, maker, best_match = row[:7]
    if not trade_id.isdigit():
        raise ValueError("CSV header or invalid trade ID")
    try:
        numbers = [Decimal(value) for value in (price, quantity, quote_quantity)]
    except InvalidOperation as error:
        raise ValueError("Invalid decimal in historical trade") from error
    if any(not number.is_finite() or number <= 0 for number in numbers):
        raise ValueError("Historical price and quantities must be finite and positive")
    if any(value.strip().lower() not in ("true", "false") for value in (maker, best_match)):
        raise ValueError("Historical maker and best_match must be true or false")
    timestamp = iso_from_epoch(int(raw_time))
    return {
        "event_id": f"binance:{symbol}:{trade_id}",
        "source": "binance",
        "symbol": symbol,
        "trade_id": int(trade_id),
        "price": price,
        "quantity": quantity,
        "quote_quantity": quote_quantity,
        "event_time": datetime.fromisoformat(timestamp.replace("Z", "+00:00")),
        "is_buyer_maker": maker.strip().lower() == "true",
        "is_best_match": best_match.strip().lower() == "true",
    }


def download_archive(session, symbol: str, month: str, directory: Path) -> Path:
    filename = f"{symbol}-trades-{month}.zip"
    target = directory / filename
    if target.exists():
        try:
            with ZipFile(target) as cached:
                if cached.testzip() is None:
                    return target
        except BadZipFile:
            pass
        target.unlink()
    url = f"{BASE_URL}/{symbol}/{filename}"
    LOG.info("Downloading %s", url)
    with session.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with NamedTemporaryFile(dir=directory, suffix=".part", delete=False) as temporary:
            pending = Path(temporary.name)
            try:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        temporary.write(chunk)
            except Exception:
                pending.unlink(missing_ok=True)
                raise
    try:
        with ZipFile(pending) as archive:
            bad_file = archive.testzip()
            if bad_file:
                raise ValueError(f"Invalid ZIP member: {bad_file}")
        pending.replace(target)
    finally:
        pending.unlink(missing_ok=True)
    return target


def import_archive(collection, archive_path: Path, symbol: str, batch_size: int, max_rows: int = 0) -> int:
    from pymongo import UpdateOne

    inserted = 0
    operations = []
    processed = 0
    with ZipFile(archive_path) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError(f"Expected one CSV in {archive_path.name}")
        with archive.open(csv_names[0]) as raw:
            reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8", newline=""))
            for row in reader:
                try:
                    document = parse_trade_row(row, symbol)
                except ValueError as error:
                    if row and row[0].lower() in ("id", "trade id", "tradeid"):
                        continue
                    raise ValueError(f"Bad row in {archive_path.name}: {error}") from error
                operations.append(UpdateOne(
                    {"symbol": symbol, "trade_id": document["trade_id"]},
                    {"$setOnInsert": document},
                    upsert=True,
                ))
                processed += 1
                if len(operations) >= batch_size:
                    inserted += collection.bulk_write(operations, ordered=False).upserted_count
                    operations.clear()
                    if processed % 100_000 == 0:
                        LOG.info("%s: %s rows processed, %s inserted", archive_path.name, processed, inserted)
                if max_rows and processed >= max_rows:
                    break
            if operations:
                inserted += collection.bulk_write(operations, ordered=False).upserted_count
    return inserted


def configured_months() -> list[str]:
    """Allow a fixed completed month for a reproducible sample import."""
    explicit = os.getenv("HISTORY_PERIODS", "").strip()
    if not explicit:
        count = int(os.getenv("HISTORY_MONTHS", "3"))
        if not 1 <= count <= 120:
            raise ValueError("HISTORY_MONTHS must be between 1 and 120")
        return previous_months(count)
    months = list(dict.fromkeys(part.strip() for part in explicit.split(",")))
    for month in months:
        parsed = datetime.strptime(month, "%Y-%m").date()
        if parsed.strftime("%Y-%m") != month or month >= date.today().strftime("%Y-%m"):
            raise ValueError("HISTORY_PERIODS must contain completed months as YYYY-MM")
    return months


def run() -> None:
    import requests
    from pymongo import MongoClient

    symbols = [part.strip().upper() for part in os.getenv("HISTORY_SYMBOLS", "BTCUSDT,ETHUSDT").split(",") if part.strip()]
    if not symbols:
        raise ValueError("HISTORY_SYMBOLS cannot be empty")
    months = configured_months()
    max_rows = int(os.getenv("HISTORY_MAX_ROWS", "0"))
    if max_rows < 0:
        raise ValueError("HISTORY_MAX_ROWS must be zero (all rows) or positive")
    batch_size = int(os.getenv("HISTORY_BATCH_SIZE", "2000"))
    if not 1 <= batch_size <= 10000:
        raise ValueError("HISTORY_BATCH_SIZE must be between 1 and 10000")
    directory = Path(os.getenv("HISTORY_DIR", "data/history"))
    directory.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "CryptoPulse/0.1 educational historical importer"
    mongo = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"), serverSelectionTimeoutMS=10000)
    collection = mongo[os.getenv("MONGO_DATABASE", "crypto_pulse")]["trades_history"]
    collection.create_index([("symbol", 1), ("trade_id", 1)], unique=True)
    collection.create_index([("symbol", 1), ("event_time", -1)])
    if max_rows:
        LOG.warning("Sample mode: at most %s rows per archive, not a full historical import", max_rows)
    for symbol in symbols:
        for month in months:
            archive = download_archive(session, symbol, month, directory)
            count = import_archive(collection, archive, symbol, batch_size, max_rows)
            LOG.info("%s %s: %s new trades", symbol, month, count)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
