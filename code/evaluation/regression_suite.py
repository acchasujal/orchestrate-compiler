"""Offline named regression suite using deterministic/fallback execution."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path
from typing import Any

from ..app.orchestrator import run_batch
from ..models import RuntimeConfig


REGRESSION_IDS = ("msg_110", "msg_040", "msg_056", "msg_021", "msg_022")


def run_regression_suite(dataset_dir: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "output.csv"
        report = run_batch(dataset_dir, output, RuntimeConfig("fallback", Path(directory) / "cache", Path(directory) / "cache", 0, True))
        with output.open(encoding="utf-8", newline="") as handle:
            rows = {row["message_id"]: row for row in csv.DictReader(handle)}
    checks = {
        "msg_110": (rows.get("msg_110", {}).get("action"), rows.get("msg_110", {}).get("message_type")) == ("mute", "scam"),
        "msg_040": (rows.get("msg_040", {}).get("action"), rows.get("msg_040", {}).get("message_type")) == ("mute", "forward"),
        "msg_056": (rows.get("msg_056", {}).get("action"), rows.get("msg_056", {}).get("message_type")) == ("notify", "urgent"),
        "msg_021": rows.get("msg_021", {}).get("action") == "notify",
        "msg_022": (rows.get("msg_022", {}).get("action"), rows.get("msg_022", {}).get("message_type")) == ("mute", "scam"),
        "msg_091": (rows.get("msg_091", {}).get("action"), rows.get("msg_091", {}).get("message_type")) == ("mute", "scam"),
        "msg_064": (rows.get("msg_064", {}).get("action"), rows.get("msg_064", {}).get("message_type")) == ("mute", "scam"),
        "msg_074": (rows.get("msg_074", {}).get("action"), rows.get("msg_074", {}).get("message_type")) == ("mute", "scam"),
        "msg_082": (rows.get("msg_082", {}).get("action"), rows.get("msg_082", {}).get("message_type")) == ("mute", "scam"),
        "msg_093": (rows.get("msg_093", {}).get("action"), rows.get("msg_093", {}).get("message_type")) == ("notify", "business_update"),
        "msg_062": (rows.get("msg_062", {}).get("action"), rows.get("msg_062", {}).get("message_type")) == ("notify", "urgent"),
    }
    return {"passed": all(checks.values()) and report.output_count == 110, "checks": checks, "batch_report": report}
