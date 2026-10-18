"""Exact-schema output construction and serialization."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence

from ..models import DecisionOutput, Justification, OutputRow


HEADER = ("message_id", "action", "message_type", "reason", "confidence", "evidence_message_ids")
VALID_ACTIONS = {"notify", "digest", "mute"}
VALID_TYPES = {"personal", "urgent", "event", "payment", "business_update", "promotion", "greeting", "forward", "spam", "scam", "unknown"}


class OutputValidationError(ValueError):
    """Final output rows violate the submission contract."""


class OutputWriteError(OSError):
    """The final output file could not be written."""


def build_output_row(decision: DecisionOutput, justification: Justification) -> OutputRow:
    evidence = ";".join(justification.evidence_message_ids) or "none"
    return OutputRow(decision.message_id, decision.action, decision.message_type, justification.reason, justification.confidence, evidence)


def validate_output(rows: Sequence[OutputRow], target_message_ids: Sequence[str]) -> None:
    expected = list(target_message_ids)
    actual = [row.message_id for row in rows]
    if len(rows) != len(expected) or actual != expected:
        raise OutputValidationError("output rows must preserve exact target coverage and order")
    if len(set(actual)) != len(actual):
        raise OutputValidationError("output contains duplicate message IDs")
    for row in rows:
        if row.action not in VALID_ACTIONS or row.message_type not in VALID_TYPES:
            raise OutputValidationError(f"invalid output enum for {row.message_id}")
        if not 0 <= row.confidence <= 1:
            raise OutputValidationError(f"invalid confidence for {row.message_id}")
        if not row.evidence_message_ids:
            raise OutputValidationError(f"empty evidence field for {row.message_id}")


def write_output(rows: Sequence[OutputRow], output_path: Path) -> None:
    try:
        with Path(output_path).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(HEADER)
            for row in rows:
                writer.writerow((row.message_id, row.action, row.message_type, row.reason, row.confidence, row.evidence_message_ids))
    except OSError as exc:
        raise OutputWriteError(f"could not write {output_path}: {exc}") from exc
