"""Download monthly Binance trades, insert idempotently and checkpoint committed batches."""

import csv
import hashlib
import io
import logging
import os
import shutil
import time
from pathlib import Path
from datetime import date, datetime, timezone
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
    import requests

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
    pending = directory / f"{filename}.part"
    for attempt in range(1, 9):
        start = pending.stat().st_size if pending.exists() else 0
        LOG.info("Downloading %s, starting at byte %s (attempt %s/8)", url, start, attempt)
        try:
            with session.get(url, stream=True, timeout=(15, 60), headers={"Range": f"bytes={start}-"} if start else {}) as response:
                # A prior transfer may have reached EOF immediately before disconnecting.
                if response.status_code == 416 and response.headers.get("Content-Range") == f"bytes */{start}":
                    pass
                else:
                    response.raise_for_status()
                    if response.status_code == 206:
                        content_range = response.headers.get("Content-Range", "")
                        if not content_range.startswith(f"bytes {start}-"):
                            raise ValueError("Server returned an unexpected byte range")
                        expected = int(content_range.rsplit("/", 1)[1])
                        mode = "ab" if start else "wb"
                    else:
                        expected = int(response.headers.get("Content-Length", "0"))
                        mode = "wb"  # Server ignored Range: replace, never append a full response.
                    last_log = time.monotonic()
                    with pending.open(mode) as temporary:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                temporary.write(chunk)
                            if time.monotonic() - last_log >= 15:
                                if shutil.disk_usage(directory).free < float(os.getenv("HISTORY_MIN_FREE_GB", "10")) * 1024**3:
                                    raise RuntimeError("History storage reserve reached; partial download retained")
                                LOG.info("%s: downloaded %s / %s bytes", filename, temporary.tell(), expected or "unknown")
                                last_log = time.monotonic()
                    if expected and pending.stat().st_size != expected:
                        raise requests.exceptions.ChunkedEncodingError("Incomplete archive response")
            with ZipFile(pending) as archive:
                bad_file = archive.testzip()
                if bad_file:
                    raise ValueError(f"Invalid ZIP member: {bad_file}")
            pending.replace(target)
            return target
        except requests.RequestException:
            if attempt == 8:
                raise
            LOG.warning("Transfer interrupted for %s; retaining partial data and retrying", filename)
            time.sleep(min(2**attempt, 30))
    raise RuntimeError("Archive download did not finish")


def import_archive(collection, archive_path: Path, symbol: str, batch_size: int, max_rows: int = 0, *, state_collection=None) -> int:
    from pymongo.errors import BulkWriteError

    inserted = 0
    operations = []
    processed = 0
    csv_records = 0
    first_trade_id = None
    last_trade_id = None
    fingerprint = None
    inserted_before = 0
    if state_collection is not None:
        with archive_path.open("rb") as raw:
            fingerprint = hashlib.file_digest(raw, "sha256").hexdigest()
        prior = state_collection.find_one({"_id": archive_path.name})
        if prior and prior.get("sha256") == fingerprint and prior.get("rows_processed", 0):
            count = collection.count_documents({"symbol": symbol, "trade_id": {
                "$gte": prior["first_trade_id"], "$lte": prior["last_trade_id"],
            }})
            if count == prior["rows_processed"]:
                if prior.get("status") == "complete" or (max_rows and prior["rows_processed"] >= max_rows):
                    LOG.info("%s: already imported (%s rows, %s)", archive_path.name, count, prior["status"])
                    return 0
                processed = prior["rows_processed"]
                csv_records = prior["csv_records"]
                first_trade_id = prior["first_trade_id"]
                last_trade_id = prior["last_trade_id"]
                inserted_before = prior.get("inserted_total", 0)
                LOG.info("%s: resuming after %s rows", archive_path.name, processed)
            else:
                LOG.warning("%s: checkpoint does not match stored data; replaying safely", archive_path.name)

    def checkpoint(status):
        if state_collection is not None:
            state_collection.update_one({"_id": archive_path.name}, {"$set": {
                "symbol": symbol, "sha256": fingerprint, "archive_bytes": archive_path.stat().st_size,
                "rows_processed": processed, "csv_records": csv_records,
                "first_trade_id": first_trade_id, "last_trade_id": last_trade_id,
                "inserted_total": inserted_before + inserted, "status": status,
                "updated_at": datetime.now(timezone.utc),
            }}, upsert=True)

    minimum_free = float(os.getenv("HISTORY_MIN_FREE_GB", "10")) * 1024**3
    last_space_check = 0

    def flush():
        nonlocal inserted, last_space_check
        if not operations:
            return
        if time.monotonic() - last_space_check >= 15:
            if shutil.disk_usage(archive_path.parent).free < minimum_free:
                raise RuntimeError("History storage reserve reached; import paused, checkpoint retained")
            last_space_check = time.monotonic()
        try:
            inserted += len(collection.insert_many(operations, ordered=False).inserted_ids)
        except BulkWriteError as error:
            details = error.details
            if details.get("writeConcernErrors") or any(item["code"] != 11000 for item in details.get("writeErrors", [])):
                raise
            duplicate_ids = {operations[item["index"]]["trade_id"] for item in details.get("writeErrors", [])}
            if duplicate_ids and collection.count_documents({"symbol": symbol, "trade_id": {"$in": list(duplicate_ids)}}) != len(duplicate_ids):
                raise  # A different unique constraint must not silently discard a new trade.
            # Equivalent to setOnInsert: retain existing trades, insert only new IDs.
            inserted += details.get("nInserted", 0)
        operations.clear()
        checkpoint("running")

    resume_records = csv_records
    limited = False
    with ZipFile(archive_path) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError(f"Expected one CSV in {archive_path.name}")
        with archive.open(csv_names[0]) as raw:
            reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8", newline=""))
            for record_number, row in enumerate(reader, 1):
                if record_number <= resume_records:
                    continue
                try:
                    document = parse_trade_row(row, symbol)
                except ValueError as error:
                    if row and row[0].lower() in ("id", "trade id", "tradeid"):
                        continue
                    raise ValueError(f"Bad row in {archive_path.name}: {error}") from error
                first_trade_id = document["trade_id"] if first_trade_id is None else first_trade_id
                last_trade_id = document["trade_id"]
                csv_records = record_number
                operations.append(document)
                processed += 1
                if len(operations) >= batch_size:
                    flush()
                    if processed % 100_000 == 0:
                        LOG.info("%s: %s rows processed, %s inserted", archive_path.name, processed, inserted)
                if max_rows and processed >= max_rows:
                    limited = True
                    break
            if operations:
                flush()
    checkpoint("sampled" if limited else "complete")
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
    if shutil.disk_usage(directory).free < float(os.getenv("HISTORY_MIN_FREE_GB", "10")) * 1024**3:
        raise RuntimeError("Insufficient free space for historical import")
    session = requests.Session()
    session.headers["User-Agent"] = "CryptoPulse/0.1 educational historical importer"
    mongo = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"), serverSelectionTimeoutMS=10000)
    collection = mongo[os.getenv("MONGO_DATABASE", "crypto_pulse")]["trades_history"]
    state_collection = mongo[os.getenv("MONGO_DATABASE", "crypto_pulse")]["history_imports"]
    collection.create_index([("symbol", 1), ("trade_id", 1)], unique=True)
    collection.create_index([("symbol", 1), ("event_time", -1)])
    if max_rows:
        LOG.warning("Sample mode: at most %s rows per archive, not a full historical import", max_rows)
    for symbol in symbols:
        for month in months:
            archive = download_archive(session, symbol, month, directory)
            count = import_archive(collection, archive, symbol, batch_size, max_rows, state_collection=state_collection)
            LOG.info("%s %s: %s new trades", symbol, month, count)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
