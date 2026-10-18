from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from code.app.orchestrator import run_batch
from code.models import RuntimeConfig


class OrchestratorTests(unittest.TestCase):
    def test_stub_batch_writes_all_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output.csv"
            report = run_batch(Path(__file__).parents[2] / "dataset", output, RuntimeConfig("stub", Path(directory) / "cache", Path(directory) / "cache", 0, True))
            self.assertTrue(report.validation_passed)
            with output.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 110)


if __name__ == "__main__":
    unittest.main()
