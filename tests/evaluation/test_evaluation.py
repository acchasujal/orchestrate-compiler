from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from code.evaluation.harness import evaluate_output
from code.evaluation.output_audit import audit_output
from code.evaluation.regression_suite import run_regression_suite
from code.evaluation.submission_audit import audit_submission


class EvaluationTests(unittest.TestCase):
    repo = Path(__file__).parents[2]

    def test_output_evaluator_accepts_generated_output(self) -> None:
        result = evaluate_output(self.repo / "dataset", self.repo / "dataset" / "output.csv")
        self.assertTrue(result["passed"])
        self.assertEqual(result["target_count"], 110)
        self.assertEqual(result["evidence_invalid"], [])

    def test_output_audit_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = audit_output(self.repo / "dataset", self.repo / "dataset" / "output.csv", Path(directory) / "OUTPUT_AUDIT.md")
            self.assertTrue(result["passed"])
            self.assertTrue((Path(directory) / "OUTPUT_AUDIT.md").is_file())

    def test_regression_suite_passes_offline(self) -> None:
        result = run_regression_suite(self.repo / "dataset")
        self.assertTrue(result["passed"])
        self.assertTrue(all(result["checks"].values()))

    def test_submission_audit_reports_exclusions(self) -> None:
        result = audit_submission(self.repo, self.repo / "dataset" / "output.csv")
        self.assertEqual(result["missing_required_files"], [])
        self.assertIn(".env", result["env_files_to_exclude"])


if __name__ == "__main__":
    unittest.main()
