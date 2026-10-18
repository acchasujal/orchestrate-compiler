"""Derive recipient-specific signals from loader-owned context and indexes."""

from __future__ import annotations

from datetime import time
from typing import Any

from ..models import DatasetTables, MessageFeatures, PersonalizationSignals, ResolvedContext


class PersonalizationInputError(ValueError):
    """A required personalization source value is malformed."""


def _integer(row: dict[str, Any], field: str) -> int:
    try:
        value = int(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise PersonalizationInputError(f"invalid integer field {field}") from exc
    if value < 0:
        raise PersonalizationInputError(f"negative integer field {field}")
    return value


def _quiet_hours_active(window: Any, created_at: Any) -> bool:
    if window in (None, ""):
        return False
    if not isinstance(window, str) or "-" not in window:
        raise PersonalizationInputError("do_not_disturb_window must use HH:MM-HH:MM")
    start_text, end_text = window.split("-", 1)
    try:
        start = time.fromisoformat(start_text)
        end = time.fromisoformat(end_text)
    except ValueError as exc:
        raise PersonalizationInputError("invalid do_not_disturb_window") from exc
    current = created_at.time()
    return current >= start or current < end if start > end else start <= current < end


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def assess_personalization(
    context: ResolvedContext,
    features: MessageFeatures,
    tables: DatasetTables,
) -> PersonalizationSignals:
    """Compute stored recipient signals without making a routing decision."""
    if context.message_id != features.message_id:
        raise PersonalizationInputError("context and features refer to different messages")

    user = context.user
    opened = _integer(user, "messages_opened_30d")
    replied = _integer(user, "messages_replied_30d")
    dismissed = _integer(user, "notifications_dismissed_30d")
    reported = _integer(user, "messages_reported_30d")
    engagement = min(1.0, 0.5 * _ratio(opened, opened + dismissed) + 0.5 * _ratio(replied, opened))

    summary = tables.daily_notification_summary.get(
        (context.user_id, context.created_at.date().isoformat()),
        {"notifications_sent": "0", "notifications_dismissed": "0"},
    )
    sent = _integer(summary, "notifications_sent")
    summary_dismissed = _integer(summary, "notifications_dismissed")
    notification_load = min(1.0, sent / 10.0 + summary_dismissed / 10.0)

    history = context.user_business_history
    opted_out = bool(
        history
        and (history.get("allows_promotions") == "0" or history.get("promotions_opted_out_at") is not None)
    )
    trusted = bool(history and _integer(history, "activity_count_180d") > 0)
    dismissal_signal = dismissed > opened or reported > 0 or bool(history and _integer(history, "messages_dismissed_30d") > 0)

    return PersonalizationSignals(
        group_muted=bool(context.group_membership and context.group_membership.get("group_muted_by_user") == "1"),
        promotions_opted_out=opted_out,
        quiet_hours_active=_quiet_hours_active(user.get("do_not_disturb_window"), context.created_at),
        recent_engagement_score=engagement,
        notification_load_score=notification_load,
        trusted_business_relationship=trusted,
        dismissal_signal=dismissal_signal,
    )
