"""Real MongoDB import recovery checks; uses and drops its own disposable database."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4
from zipfile import ZipFile

from scripts.historical_loader import import_archive


@unittest.skipUnless(os.getenv("MONGO_TEST_URI"), "Set MONGO_TEST_URI to run disposable MongoDB checks")
class HistoryRecoveryTests(unittest.TestCase):
    def setUp(self):
        from pymongo import MongoClient

        self.client = MongoClient(os.environ["MONGO_TEST_URI"], serverSelectionTimeoutMS=5000)
        self.name = "cryptopulse_test_" + uuid4().hex
        self.db = self.client[self.name]
        self.trades = self.db.trades
        self.trades.create_index([("symbol", 1), ("trade_id", 1)], unique=True)
        self.temporary = TemporaryDirectory()
        self.archive = Path(self.temporary.name) / "TESTBTC-trades-2025-01.zip"
        self.write_archive(5)

    def tearDown(self):
        self.client.drop_database(self.name)
        self.client.close()
        self.temporary.cleanup()

    def write_archive(self, count):
        rows = [f"{i},100.0,0.2,20.0,{1735689600000000+i},false,true" for i in range(1, count + 1)]
        with ZipFile(self.archive, "w") as archive:
            archive.writestr("trades.csv", "id,price,qty,quoteQty,time,maker,bestMatch\n" + "\n".join(rows))

    def load(self, limit=0, state=None):
        return import_archive(self.trades, self.archive, "TESTBTC", 2, limit,
                              state_collection=self.db.history_imports if state is None else state)

    def test_sample_then_resume_and_skip_complete_archive(self):
        self.assertEqual(self.load(2), 2)
        self.assertEqual(self.db.history_imports.find_one()["status"], "sampled")
        self.assertEqual(self.load(), 3)
        self.assertEqual(self.load(), 0)
        self.assertEqual(self.trades.count_documents({}), 5)
        state = self.db.history_imports.find_one()
        self.assertEqual(state["rows_processed"], 5)
        self.assertEqual(state["csv_records"], 6)  # Header survives restart without shifting the cursor.
        self.assertEqual(state["status"], "complete")

    def test_failed_checkpoint_replays_committed_batch_without_duplicates(self):
        state = self.db.history_imports
        with patch.object(state, "update_one", side_effect=RuntimeError("interrupted checkpoint")):
            with self.assertRaises(RuntimeError):
                self.load(state=state)
        self.assertEqual(self.trades.count_documents({}), 2)
        self.assertEqual(self.load(), 3)
        self.assertEqual(self.trades.count_documents({}), 5)

    def test_missing_data_invalidates_checkpoint(self):
        self.load()
        self.trades.delete_one({"trade_id": 3})
        self.assertEqual(self.load(), 1)
        self.assertEqual(self.trades.count_documents({}), 5)

    def test_changed_archive_invalidates_fingerprint(self):
        self.load()
        self.write_archive(6)
        self.assertEqual(self.load(), 1)
        self.assertEqual(self.trades.count_documents({}), 6)

    def test_unrelated_unique_constraint_is_not_silently_ignored(self):
        from pymongo.errors import BulkWriteError

        self.trades.create_index("price", unique=True)
        with self.assertRaises(BulkWriteError):
            self.load()
        self.assertIsNone(self.db.history_imports.find_one())
