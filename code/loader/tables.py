"""Strict, deterministic loading of the participant-facing dataset."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..models import DatasetTables, MediaCatalog
from .schemas import DatasetReadError, DatasetSchemaError


REQUIRED_HEADERS: dict[str, tuple[str, ...]] = {
    "messages.csv": (
        "message_id", "user_id", "conversation_type", "group_id", "business_id",
        "sender_user_id", "created_at", "message_text", "media_type", "media_id",
        "forwarded_count",
    ),
    "sample_messages.csv": (
        "message_id", "user_id", "conversation_type", "group_id", "business_id",
        "sender_user_id", "created_at", "message_text", "media_type", "media_id",
        "forwarded_count", "action", "message_type", "reason", "confidence",
        "evidence_message_ids",
    ),
    "users.csv": (
        "user_id", "do_not_disturb_window", "messages_opened_30d", "messages_replied_30d",
        "notifications_dismissed_30d", "messages_reported_30d",
    ),
    "groups.csv": (
        "group_id", "group_name", "group_type", "member_count", "admin_count",
        "created_at", "messages_30d",
    ),
    "group_members.csv": (
        "group_id", "user_id", "role", "joined_at", "messages_sent_30d",
        "messages_read_30d", "replies_sent_30d", "notifications_dismissed_30d",
        "group_muted_by_user",
    ),
    "business_accounts.csv": (
        "business_id", "display_name", "brand_name", "category", "verified",
        "official_domain", "domain_used_by_sender", "account_age_days", "messages_sent_30d",
        "user_reports_30d", "domain_used_by_sender_age_days",
    ),
    "user_business_history.csv": (
        "user_id", "business_id", "why_user_knows_account", "last_activity_at",
        "allows_promotions", "promotions_opted_out_at", "activity_count_180d",
        "messages_opened_30d", "messages_dismissed_30d", "messages_replied_30d", "last_reply_at",
    ),
    "message_history.csv": (
        "message_id", "user_id", "conversation_type", "group_id", "business_id",
        "sender_user_id", "created_at", "message_text", "media_type", "media_id",
        "forwarded_count",
    ),
    "message_events.csv": (
        "user_id", "message_id", "message_opened", "message_replied", "reaction_time_minutes",
        "notification_dismissed", "muted_after_message", "message_reported",
    ),
    "images.csv": ("image_id", "file_path"),
    "voice_notes.csv": ("voice_note_id", "file_path"),
    "daily_notification_summary.csv": (
        "user_id", "date", "notifications_sent", "notifications_dismissed",
    ),
    "output.csv": (
        "message_id", "action", "message_type", "reason", "confidence", "evidence_message_ids",
    ),
}

REQUIRED_FILES = tuple(REQUIRED_HEADERS)
EMPTY_TO_NONE_FIELDS = {
    "group_id", "business_id", "sender_user_id", "message_text", "media_type", "media_id",
    "official_domain", "domain_used_by_sender", "promotions_opted_out_at", "last_reply_at",
    "reaction_time_minutes", "file_path", "do_not_disturb_window",
}


@dataclass(frozen=True)
class ValidationSummary:
    rows_loaded: Mapping[str, int]
    media_discovered: Mapping[str, int]
    duplicate_keys: int
    missing_references: int
    warnings: tuple[str, ...]


def _normalize_row(row: Mapping[str, str]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        normalized[key] = None if key in EMPTY_TO_NONE_FIELDS and value == "" else value
    return normalized


def _read_csv(dataset_dir: Path, filename: str) -> list[dict[str, Any]]:
    path = dataset_dir / filename
    if not path.is_file():
        raise DatasetReadError(f"required dataset file is missing: {path}")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            actual = tuple(reader.fieldnames or ())
            expected = REQUIRED_HEADERS[filename]
            if actual != expected:
                raise DatasetSchemaError(
                    f"{filename} headers differ; expected {expected}, got {actual}"
                )
            return [_normalize_row(row) for row in reader]
    except DatasetSchemaError:
        raise
    except (OSError, csv.Error) as exc:
        raise DatasetReadError(f"could not read {path}: {exc}") from exc


def _require_nonempty(rows: Iterable[Mapping[str, Any]], filename: str, field: str) -> None:
    for index, row in enumerate(rows, start=2):
        if row.get(field) in (None, ""):
            raise DatasetSchemaError(f"{filename} row {index} has empty required field {field}")


def _keyed(
    rows: list[dict[str, Any]], filename: str, fields: tuple[str, ...]
) -> dict[Any, dict[str, Any]]:
    keyed_rows: dict[Any, dict[str, Any]] = {}
    for index, row in enumerate(rows, start=2):
        _require_nonempty((row,), filename, fields[0])
        key_values = tuple(row.get(field) for field in fields)
        if any(value in (None, "") for value in key_values):
            raise DatasetSchemaError(f"{filename} row {index} has incomplete key {fields}")
        key = key_values[0] if len(fields) == 1 else key_values
        if key in keyed_rows:
            raise DatasetSchemaError(f"{filename} contains duplicate key {key!r}")
        keyed_rows[key] = row
    return keyed_rows


def _validate_messages(
    rows: list[dict[str, Any]], filename: str, users: Mapping[str, Any],
    groups: Mapping[str, Any], businesses: Mapping[str, Any],
    group_members: Mapping[tuple[str, str], Any], images: Mapping[str, Path],
    voice_notes: Mapping[str, Path],
) -> None:
    for index, row in enumerate(rows, start=2):
        media_type = row.get("media_type")
        media_id = row.get("media_id")
        if media_type not in (None, "image", "voice"):
            raise DatasetSchemaError(f"{filename} row {index} has invalid media_type {media_type!r}")
        if (media_type is None) != (media_id is None):
            raise DatasetSchemaError(f"{filename} row {index} has inconsistent media fields")
        if media_type == "image" and media_id not in images:
            raise DatasetSchemaError(f"{filename} row {index} references missing image {media_id!r}")
        if media_type == "voice" and media_id not in voice_notes:
            raise DatasetSchemaError(f"{filename} row {index} references missing voice note {media_id!r}")
        user_id = row.get("user_id")
        if user_id not in users:
            raise DatasetSchemaError(f"{filename} row {index} references missing user {user_id!r}")
        sender = row.get("sender_user_id")
        if sender is not None and sender not in users:
            raise DatasetSchemaError(f"{filename} row {index} references missing sender {sender!r}")
        group_id = row.get("group_id")
        if group_id is not None:
            if group_id not in groups:
                raise DatasetSchemaError(f"{filename} row {index} references missing group {group_id!r}")
            if (group_id, user_id) not in group_members:
                raise DatasetSchemaError(f"{filename} row {index} lacks group membership for {user_id!r}")
        business_id = row.get("business_id")
        if business_id is not None and business_id not in businesses:
            raise DatasetSchemaError(f"{filename} row {index} references missing business {business_id!r}")
        if not isinstance(row.get("forwarded_count"), str) or not row["forwarded_count"].isdigit():
            raise DatasetSchemaError(f"{filename} row {index} has invalid forwarded_count")


def _validate_media_catalog(
    dataset_dir: Path, rows: list[dict[str, Any]], filename: str
) -> dict[str, Path]:
    catalog: dict[str, Path] = {}
    for index, row in enumerate(rows, start=2):
        key = row.get("image_id") or row.get("voice_note_id")
        relative = row.get("file_path")
        if not key or not relative:
            raise DatasetSchemaError(f"{filename} row {index} has incomplete media catalog data")
        candidate = (dataset_dir / relative).resolve()
        media_root = (dataset_dir / "media").resolve()
        if media_root not in candidate.parents:
            raise DatasetSchemaError(f"{filename} row {index} escapes dataset media directory")
        if not candidate.is_file():
            raise DatasetSchemaError(f"{filename} row {index} references missing file {candidate}")
        if key in catalog:
            raise DatasetSchemaError(f"{filename} contains duplicate key {key!r}")
        catalog[key] = candidate
    return catalog


def _validate_events(rows: list[dict[str, Any]], history: Mapping[str, Any], users: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    keyed = _keyed(rows, "message_events.csv", ("user_id", "message_id"))
    for key, row in keyed.items():
        user_id, message_id = key
        if user_id not in users:
            raise DatasetSchemaError(f"message_events.csv references missing user {user_id!r}")
        history_row = history.get(message_id)
        if history_row is None or history_row.get("user_id") != user_id:
            raise DatasetSchemaError(f"message_events.csv references invalid history message {key!r}")
    return keyed


def _validate_history(
    rows: list[dict[str, Any]],
    users: Mapping[str, Any],
    groups: Mapping[str, Any],
    businesses: Mapping[str, Any],
    group_members: Mapping[tuple[str, str], Any],
    images: Mapping[str, Path],
    voice_notes: Mapping[str, Path],
) -> dict[str, dict[str, Any]]:
    keyed = _keyed(rows, "message_history.csv", ("message_id",))
    _validate_messages(
        rows, "message_history.csv", users, groups, businesses, group_members, images, voice_notes
    )
    return keyed


def load_dataset(dataset_dir: Path) -> tuple[DatasetTables, MediaCatalog]:
    """Load and validate all participant-facing tables and media catalogs."""
    dataset_dir = Path(dataset_dir)
    if not dataset_dir.is_dir():
        raise DatasetReadError(f"dataset directory is missing: {dataset_dir}")

    loaded = {filename: _read_csv(dataset_dir, filename) for filename in REQUIRED_FILES}
    users = _keyed(loaded["users.csv"], "users.csv", ("user_id",))
    groups = _keyed(loaded["groups.csv"], "groups.csv", ("group_id",))
    group_members = _keyed(loaded["group_members.csv"], "group_members.csv", ("group_id", "user_id"))
    businesses = _keyed(loaded["business_accounts.csv"], "business_accounts.csv", ("business_id",))
    business_history = _keyed(loaded["user_business_history.csv"], "user_business_history.csv", ("user_id", "business_id"))
    images = _validate_media_catalog(dataset_dir, loaded["images.csv"], "images.csv")
    voice_notes = _validate_media_catalog(dataset_dir, loaded["voice_notes.csv"], "voice_notes.csv")
    history = _validate_history(
        loaded["message_history.csv"],
        users,
        groups,
        businesses,
        group_members,
        images,
        voice_notes,
    )
    events = _validate_events(loaded["message_events.csv"], history, users)
    for row in loaded["user_business_history.csv"]:
        business_id = row["business_id"]
        if row["user_id"] not in users or business_id not in businesses:
            raise DatasetSchemaError(f"user_business_history.csv references invalid relationship {(row['user_id'], business_id)!r}")
    for row in loaded["daily_notification_summary.csv"]:
        if row["user_id"] not in users:
            raise DatasetSchemaError(f"daily_notification_summary.csv references missing user {row['user_id']!r}")
    _keyed(loaded["messages.csv"], "messages.csv", ("message_id",))
    _keyed(loaded["sample_messages.csv"], "sample_messages.csv", ("message_id",))
    _keyed(loaded["output.csv"], "output.csv", ("message_id",))
    _validate_messages(loaded["messages.csv"], "messages.csv", users, groups, businesses, group_members, images, voice_notes)
    _validate_messages(loaded["sample_messages.csv"], "sample_messages.csv", users, groups, businesses, group_members, images, voice_notes)

    tables = DatasetTables(
        messages=tuple(loaded["messages.csv"]),
        sample_messages=tuple(loaded["sample_messages.csv"]),
        users=users,
        groups=groups,
        group_members=group_members,
        business_accounts=businesses,
        user_business_history=business_history,
        message_history=history,
        message_events=events,
        daily_notification_summary=_keyed(loaded["daily_notification_summary.csv"], "daily_notification_summary.csv", ("user_id", "date")),
    )
    return tables, MediaCatalog(images=images, voice_notes=voice_notes)
