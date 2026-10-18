import csv
import tempfile
import unittest
from pathlib import Path

from code.app.orchestrator import run_batch
from code.models import RuntimeConfig


class FinalKnowledgeRegressionTests(unittest.TestCase):
    repo = Path(__file__).resolve().parents[2]

    def test_confirmed_final_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output.csv"
            run_batch(self.repo / "dataset", output, RuntimeConfig("fallback", Path(directory) / "cache", Path(directory) / "cache", 0, True))
            with output.open(encoding="utf-8", newline="") as handle:
                rows = {row["message_id"]: row for row in csv.DictReader(handle)}
        expected = {
            "msg_018": ("mute", "scam"),
            "msg_048": ("mute", "scam"),
            "msg_091": ("mute", "scam"),
            "msg_064": ("mute", "scam"),
            "msg_074": ("mute", "scam"),
            "msg_082": ("mute", "scam"),
            "msg_093": ("notify", "business_update"),
            "msg_062": ("notify", "urgent"),
        }
        for message_id, pair in expected.items():
            self.assertEqual((rows[message_id]["action"], rows[message_id]["message_type"]), pair, message_id)
