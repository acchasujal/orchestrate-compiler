from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from code.justification import justify
from code.models import DecisionOutput
from code.output import build_output_row, validate_output, write_output


class OutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.decision = DecisionOutput("m1", "mute", "scam", "hard_safety_override", ("otp",))

    def test_justification_is_decision_consistent(self) -> None:
        row = build_output_row(self.decision, justify(self.decision, ()))
        self.assertEqual(row.evidence_message_ids, "none")
        self.assertEqual(row.action, "mute")

    def test_output_validation_preserves_order(self) -> None:
        row = build_output_row(self.decision, justify(self.decision, ()))
        validate_output([row], ["m1"])
        with self.assertRaises(ValueError):
            validate_output([row], ["m2"])

    def test_writer_has_exact_header(self) -> None:
        row = build_output_row(self.decision, justify(self.decision, ()))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "output.csv"
            write_output([row], path)
            with path.open(newline="", encoding="utf-8") as handle:
                self.assertEqual(next(csv.reader(handle)), ["message_id", "action", "message_type", "reason", "confidence", "evidence_message_ids"])


if __name__ == "__main__":
    unittest.main()
