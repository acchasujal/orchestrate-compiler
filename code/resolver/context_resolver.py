"""Deterministic resolution of message identity and direct relationships."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from ..models import DatasetTables, ResolvedContext


class ContextResolutionError(ValueError):
    """A required identity or conversation relationship is invalid."""


def _required(row: Mapping[str, Any], field: str) -> Any:
    value = row.get(field)
    if value in (None, ""):
        raise ContextResolutionError(f"message is missing required field {field}")
    return value


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ContextResolutionError("message created_at must be a non-empty ISO timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContextResolutionError(f"invalid message timestamp: {value!r}") from exc


def resolve_context(message: Mapping[str, Any], tables: DatasetTables) -> ResolvedContext:
    """Resolve one message using only loader-owned indexes."""
    message_id = _required(message, "message_id")
    user_id = _required(message, "user_id")
    conversation_type = _required(message, "conversation_type")
    if conversation_type not in ("personal", "group", "business"):
        raise ContextResolutionError(f"invalid conversation_type: {conversation_type!r}")
    created_at = _timestamp(_required(message, "created_at"))

    user = tables.users.get(user_id)
    if user is None:
        raise ContextResolutionError(f"unknown recipient user_id: {user_id!r}")

    group_id = message.get("group_id")
    business_id = message.get("business_id")
    sender_user_id = message.get("sender_user_id")

    if conversation_type == "group":
        if group_id is None:
            raise ContextResolutionError("group messages require group_id")
        if business_id is not None:
            raise ContextResolutionError("group messages cannot contain business_id")
        if sender_user_id is None:
            raise ContextResolutionError("group messages require sender_user_id")
    elif conversation_type == "business":
        if business_id is None:
            raise ContextResolutionError("business messages require business_id")
        if group_id is not None:
            raise ContextResolutionError("business messages cannot contain group_id")
    else:
        if group_id is not None or business_id is not None:
            raise ContextResolutionError("personal messages cannot contain group_id or business_id")
        if sender_user_id is None:
            raise ContextResolutionError("personal messages require sender_user_id")

    sender = None
    if sender_user_id is not None:
        sender = tables.users.get(sender_user_id)
        if sender is None:
            raise ContextResolutionError(f"unknown sender_user_id: {sender_user_id!r}")

    group = None
    group_membership = None
    if group_id is not None:
        group = tables.groups.get(group_id)
        if group is None:
            raise ContextResolutionError(f"unknown group_id: {group_id!r}")
        group_membership = tables.group_members.get((group_id, user_id))
        if group_membership is None:
            raise ContextResolutionError(
                f"recipient {user_id!r} is not a member of group {group_id!r}"
            )

    business = None
    user_business_history = None
    if business_id is not None:
        business = tables.business_accounts.get(business_id)
        if business is None:
            raise ContextResolutionError(f"unknown business_id: {business_id!r}")
        user_business_history = tables.user_business_history.get((user_id, business_id))

    return ResolvedContext(
        message_id=message_id,
        user_id=user_id,
        conversation_type=conversation_type,
        created_at=created_at,
        group_id=group_id,
        business_id=business_id,
        sender_user_id=sender_user_id,
        user=user,
        sender=sender,
        group=group,
        group_membership=group_membership,
        business=business,
        user_business_history=user_business_history,
    )
