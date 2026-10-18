"""Offline evaluation of output shape, coverage, evidence, and calibration."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any

from ..loader import load_dataset
from ..output.output_writer import HEADER, VALID_ACTIONS, VALID_TYPES


def _read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def evaluate_output(dataset_dir: Path, output_path: Path) -> dict[str, Any]:
    tables, _ = load_dataset(dataset_dir)
    header, rows = _read_rows(output_path)
    target_rows = list(tables.messages)
    target_ids = [str(row["message_id"]) for row in target_rows]
    target_users = {str(row["message_id"]): str(row["user_id"]) for row in target_rows}
    history_users = {message_id: str(row["user_id"]) for message_id, row in tables.message_history.items()}
    actual_ids = [row.get("message_id", "") for row in rows]
    evidence_invalid: list[str] = []
    enum_invalid: list[str] = []
    confidence_invalid: list[str] = []
    empty_reason: list[str] = []
    for row in rows:
        message_id = row.get("message_id", "")
        if row.get("action") not in VALID_ACTIONS or row.get("message_type") not in VALID_TYPES:
            enum_invalid.append(message_id)
        try:
            confidence = float(row.get("confidence", ""))
            if not 0 <= confidence <= 1:
                raise ValueError
        except (TypeError, ValueError):
            confidence_invalid.append(message_id)
        if not row.get("reason", "").strip():
            empty_reason.append(message_id)
        evidence = row.get("evidence_message_ids", "")
        if evidence != "none":
            for evidence_id in evidence.split(";"):
                if evidence_id not in history_users or history_users[evidence_id] != target_users.get(message_id):
                    evidence_invalid.append(f"{message_id}:{evidence_id}")
    duplicate_ids = [message_id for message_id, count in Counter(actual_ids).items() if count > 1]
    missing_ids = [message_id for message_id in target_ids if message_id not in actual_ids]
    extra_ids = [message_id for message_id in actual_ids if message_id not in target_ids]
    confidence_values = []
    for row in rows:
        try:
            confidence_values.append(float(row["confidence"]))
        except (KeyError, ValueError):
            pass
    reason_counter = Counter(row.get("reason", "") for row in rows)
    exact_duplicate_rows = sum(count - 1 for count in Counter(tuple(row.get(column, "") for column in header) for row in rows).values() if count > 1)
    exact_target_accuracy = None
    return {
        "passed": bool(
            header == list(HEADER)
            and len(rows) == len(target_rows)
            and actual_ids == target_ids
            and not duplicate_ids
            and not missing_ids
            and not extra_ids
            and not enum_invalid
            and not confidence_invalid
            and not empty_reason
            and not evidence_invalid
        ),
        "header_ok": header == list(HEADER),
        "target_count": len(target_rows),
        "output_count": len(rows),
        "missing_ids": missing_ids,
        "extra_ids": extra_ids,
        "duplicate_ids": duplicate_ids,
        "enum_invalid": enum_invalid,
        "confidence_invalid": confidence_invalid,
        "empty_reason": empty_reason,
        "evidence_invalid": evidence_invalid,
        "confidence_min": min(confidence_values) if confidence_values else None,
        "confidence_max": max(confidence_values) if confidence_values else None,
        "confidence_extremes": sum(value >= 0.95 or value <= 0.05 for value in confidence_values),
        "unique_reason_count": len(reason_counter),
        "max_repeated_reason_count": max(reason_counter.values()) if reason_counter else 0,
        "exact_duplicate_rows": exact_duplicate_rows,
        "exact_target_accuracy": exact_target_accuracy,
        "sample_accuracy_available": False,
        "sample_accuracy_note": "sample_messages.csv uses a distinct message namespace and cannot score target output rows directly",
    }
