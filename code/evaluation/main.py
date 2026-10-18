"""Run offline evaluation, regression, output, and submission audits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .output_audit import audit_output
from .regression_suite import run_regression_suite
from .submission_audit import audit_submission
from .gemini_usage_audit import render_usage_audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--report-dir", type=Path, default=Path("validation_reports"))
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = (args.output or repo / "dataset" / "output.csv").resolve()
    args.report_dir.mkdir(parents=True, exist_ok=True)
    regression = run_regression_suite(repo / "dataset")
    result = {
        "regression": regression,
        "output": audit_output(repo / "dataset", output, args.report_dir / "OUTPUT_AUDIT.md"),
        "submission": audit_submission(repo, output),
    }
    batch_report = result["regression"]["batch_report"]
    result["gemini_usage"] = render_usage_audit(batch_report, args.report_dir / "GEMINI_USAGE_AUDIT.md")
    result["regression"]["batch_report"] = vars(batch_report)
    result["regression"]["batch_report"]["output_path"] = str(result["regression"]["batch_report"]["output_path"])
    (args.report_dir / "validation.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["output"]["passed"] and result["regression"]["passed"] and result["submission"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
