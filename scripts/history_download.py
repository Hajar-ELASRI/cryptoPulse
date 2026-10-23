"""Stage the same Binance monthly archives without requiring Docker or MongoDB."""

import json
import logging
import os
from pathlib import Path
import shutil
from zipfile import ZipFile

from scripts.historical_loader import configured_months, download_archive


def run() -> None:
    import requests

    symbols = [part.strip().upper() for part in os.getenv("HISTORY_SYMBOLS", "BTCUSDT,ETHUSDT").split(",") if part.strip()]
    if not symbols:
        raise ValueError("HISTORY_SYMBOLS cannot be empty")
    directory = Path(os.getenv("HISTORY_DIR", "data/history"))
    directory.mkdir(parents=True, exist_ok=True)
    minimum_free = float(os.getenv("HISTORY_MIN_FREE_GB", "10")) * 1024**3
    inventory = []
    with requests.Session() as session:
        for symbol in symbols:
            for month in configured_months():
                if shutil.disk_usage(directory).free < minimum_free:
                    raise RuntimeError("Storage reserve reached; partial downloads retained")
                path = download_archive(session, symbol, month, directory)
                with ZipFile(path) as archive:
                    csv_bytes = sum(info.file_size for info in archive.infolist())
                item = {"symbol": symbol, "month": month, "file": path.name,
                        "zip_bytes": path.stat().st_size, "csv_bytes": csv_bytes}
                inventory.append(item)
                logging.info("Archive ready: %s", path.name)
                # Persist the inventory after each successful archive, including partial runs.
                pending = directory / "download-inventory.json.tmp"
                pending.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
                pending.replace(directory / "download-inventory.json")
    print(json.dumps(inventory, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
