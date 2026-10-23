"""Read archive checkpoints and optionally confirm their MongoDB trade counts."""

import argparse
import json
import os
from pathlib import Path

from scripts.historical_loader import configured_months


def main() -> int:
    from pymongo import MongoClient

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Count stored trades for each checkpoint ID range")
    parser.add_argument("--require-complete", action="store_true", help="Exit 1 until every planned archive is complete")
    args = parser.parse_args()
    symbols = [part.strip().upper() for part in os.getenv("HISTORY_SYMBOLS", "BTCUSDT,ETHUSDT").split(",") if part.strip()]
    directory = Path(os.getenv("HISTORY_DIR", "data/history"))
    entries = []
    with MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"), serverSelectionTimeoutMS=10000) as client:
        db = client[os.getenv("MONGO_DATABASE", "crypto_pulse")]
        for symbol in symbols:
            for month in configured_months():
                name = f"{symbol}-trades-{month}.zip"
                state = db.history_imports.find_one({"_id": name})
                entry = {"archive": name, "symbol": symbol, "month": month}
                if state:
                    entry.update({key: state.get(key) for key in ("status", "rows_processed", "updated_at")})
                    if args.verify and state.get("rows_processed", 0):
                        entry["stored_count"] = db.trades_history.count_documents({"symbol": symbol, "trade_id": {
                            "$gte": state["first_trade_id"], "$lte": state["last_trade_id"],
                        }})
                        entry["matches_checkpoint"] = entry["stored_count"] == state["rows_processed"]
                else:
                    entry["rows_processed"] = 0
                    if (directory / name).exists():
                        entry["status"] = "downloaded"
                    elif (directory / (name + ".part")).exists():
                        entry["status"] = "partial_download"
                        entry["downloaded_bytes"] = (directory / (name + ".part")).stat().st_size
                    else:
                        entry["status"] = "pending"
                entries.append(entry)
    complete = bool(entries) and all(entry["status"] == "complete" and entry.get("matches_checkpoint", True) for entry in entries)
    print(json.dumps({"all_complete": complete, "counts_verified": args.verify,
                      "rows_processed_total": sum(entry["rows_processed"] for entry in entries),
                      "archives": entries}, default=str, indent=2))
    return 0 if complete or not args.require_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
