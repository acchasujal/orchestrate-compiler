"""Human-readable output audit built on the offline evaluator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .harness import evaluate_output


def audit_output(dataset_dir: Path, output_path: Path, report_path: Path | None = None) -> dict[str, Any]:
    result = evaluate_output(dataset_dir, output_path)
    if report_path is not None:
        lines = ["# Output Audit", "", f"- Passed: `{result['passed']}`", f"- Header valid: `{result['header_ok']}`", f"- Rows: `{result['output_count']}/{result['target_count']}`", ""]
        for field in ("missing_ids", "extra_ids", "duplicate_ids", "enum_invalid", "confidence_invalid", "empty_reason", "evidence_invalid"):
            lines.append(f"- {field}: `{len(result[field])}`")
        lines.extend(["", f"- Confidence range: `{result['confidence_min']}` to `{result['confidence_max']}`", f"- Extreme confidence rows: `{result['confidence_extremes']}`", f"- Unique reasons: `{result['unique_reason_count']}`", f"- Exact duplicate rows: `{result['exact_duplicate_rows']}`", "", f"- Note: {result['sample_accuracy_note']}"])
        Path(report_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
