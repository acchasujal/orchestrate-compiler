"""Deterministic extraction of directly observable message features."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from ..models import MessageFeatures, Observation, ResolvedContext
from ..knowledge import SemanticKnowledge


_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_PAYMENT = re.compile(r"\b(?:pay|payment|transfer|upi|refund|invoice|fee|amount|bank)\b", re.IGNORECASE)
_OTP = re.compile(r"\b(?:otp|one[- ]time|verification|verify|security code|login code)\b", re.IGNORECASE)
_FORWARD = re.compile(r"\b(?:forward|share|send this to|blessings|chain message|do not ignore)\b", re.IGNORECASE)
_URGENT = re.compile(r"\b(?:urgent|asap|immediately|right now|today|just now|emergency|before|within\s+\d+|next\s+(?:\d+|ten|twenty)\s+(?:min|mins|minutes|hour|hours)|by\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", re.IGNORECASE)


def _knowledge_root() -> Any:
    return Path(__file__).resolve().parents[2]


def _content_text(observation: Observation, message_text: Any) -> str | None:
    if message_text not in (None, ""):
        return str(message_text)
    if observation.image is not None:
        return observation.image.ocr_text
    if observation.voice is not None:
        return observation.voice.transcript
    return None


def _forwarded_count(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("forwarded_count must be an integer, not bool")
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("forwarded_count must be an integer") from exc
    if count < 0:
        raise ValueError("forwarded_count cannot be negative")
    return count


def extract_features(
    context: ResolvedContext,
    message: Mapping[str, Any],
    observation: Observation,
) -> MessageFeatures:
    """Extract only deterministic signals present in the message or observation."""
    content = _content_text(observation, message.get("message_text"))
    searchable = content or ""
    media_type = message.get("media_type")
    media_id = message.get("media_id")
    if media_type not in (None, "image", "voice"):
        raise ValueError(f"unsupported media_type: {media_type!r}")
    if (media_type is None) != (media_id is None):
        raise ValueError("media_type and media_id must be present together")
    if observation.media_type != media_type:
        raise ValueError("observation modality does not match message")
    semantic = SemanticKnowledge(_knowledge_root()).enrich(media_id, content)
    return MessageFeatures(
        message_id=context.message_id,
        message_text=message.get("message_text"),
        media_type=media_type,
        media_id=media_id,
        forwarded_count=_forwarded_count(message.get("forwarded_count")),
        content_text=content,
        mentions_recipient=f"@{context.user_id}" in searchable,
        has_url=bool(_URL.search(searchable)),
        has_payment_language=bool(_PAYMENT.search(searchable)),
        has_otp_or_verification_language=bool(_OTP.search(searchable)),
        has_forward_or_chain_language=bool(_FORWARD.search(searchable)),
        has_urgent_language=bool(_URGENT.search(searchable)) or "urgent" in semantic["tags"],
        semantic_tags=semantic["tags"],
        transactional_signal=semantic["transactional"],
        promotional_signal=semantic["promotional"],
        sensitive_request=semantic["sensitive_request"],
        payment_request=semantic["payment_request"],
        explicit_safe_payment=semantic["explicit_safe_payment"],
        media_conflict=semantic["media_conflict"],
    )
