"""Small deterministic evidence selector over the historical corpus."""

from __future__ import annotations

import re
from typing import Any

from ..models import DatasetTables, EvidenceReference, MessageFeatures, ResolvedContext

_TOKEN = re.compile(r"[a-z0-9]{3,}")
_STOP = {"the", "and", "for", "this", "that", "with", "from", "your", "you", "are", "was", "has"}


def _tokens(value: Any) -> set[str]:
    return {token for token in _TOKEN.findall(str(value or "").lower()) if token not in _STOP}


def retrieve_evidence(context: ResolvedContext, features: MessageFeatures, tables: DatasetTables) -> tuple[EvidenceReference, ...]:
    current_tokens = _tokens(features.content_text)
    candidates: list[tuple[float, str, str]] = []
    for message_id, row in tables.message_history.items():
        if row.get("user_id") != context.user_id:
            continue
        score = 0.0
        reasons: list[str] = []
        if context.business_id and row.get("business_id") == context.business_id:
            score += 0.50
            reasons.append("same business")
        if context.group_id and row.get("group_id") == context.group_id:
            score += 0.35
            reasons.append("same group")
        if context.sender_user_id and row.get("sender_user_id") == context.sender_user_id:
            score += 0.40
            reasons.append("same sender")
        if row.get("conversation_type") == context.conversation_type:
            score += 0.05
        overlap = len(current_tokens & _tokens(row.get("message_text")))
        if overlap:
            score += min(0.35, overlap * 0.07)
            reasons.append("matching content terms")
        if features.has_otp_or_verification_language and re.search(r"\b(?:otp|verify|verification|login)\b", str(row.get("message_text") or ""), re.I):
            score += 0.25
            reasons.append("matching verification pattern")
        if features.has_payment_language and re.search(r"\b(?:pay|payment|upi|bank|invoice|refund)\b", str(row.get("message_text") or ""), re.I):
            score += 0.20
            reasons.append("matching payment pattern")
        if features.has_forward_or_chain_language and int(row.get("forwarded_count") or 0) > 0:
            score += 0.15
            reasons.append("matching forwarded pattern")
        if score >= 0.35:
            event = tables.message_events.get((context.user_id, message_id))
            if event:
                if event.get("message_reported") == "1":
                    reasons.append("previously reported")
                if event.get("notification_dismissed") == "1":
                    reasons.append("previously dismissed")
                if event.get("muted_after_message") == "1":
                    reasons.append("muted after message")
            candidates.append((min(score, 1.0), message_id, "; ".join(reasons)))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return tuple(EvidenceReference(message_id, context.user_id, reason, score) for score, message_id, reason in candidates[:3])
