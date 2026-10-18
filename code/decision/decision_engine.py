"""Frozen deterministic routing gate chain."""

from __future__ import annotations

from ..models import DecisionInput, DecisionOutput


class DecisionInputError(ValueError):
    """The decision engine received an incomplete or inconsistent input."""


def _message_type_for_risk(inputs: DecisionInput) -> str:
    if inputs.risk.is_scam_like or inputs.features.has_otp_or_verification_language:
        return "scam"
    if inputs.risk.is_spam_like or inputs.features.has_forward_or_chain_language:
        return "spam"
    return "scam"


def _ordinary_message_type(inputs: DecisionInput) -> str:
    tags = set(inputs.features.semantic_tags)
    if inputs.features.transactional_signal and inputs.context.conversation_type == "business":
        return "business_update"
    if inputs.features.explicit_safe_payment or inputs.features.has_payment_language:
        return "payment"
    if "event" in tags or inputs.features.media_type == "image" and "calendar" in tags:
        return "event"
    if inputs.features.has_forward_or_chain_language:
        return "forward"
    return "urgent" if inputs.features.has_urgent_language else "personal"


def decide(inputs: DecisionInput) -> DecisionOutput:
    """Apply the architecture's gate priority to typed upstream signals."""
    if inputs.risk.hard_override:
        return DecisionOutput(
            message_id=inputs.context.message_id,
            action="mute",
            message_type=_message_type_for_risk(inputs),
            fired_gate="hard_safety_override",
            matched_signals=inputs.risk.matched_rules,
        )

    if "missing_person" in inputs.features.semantic_tags:
        return DecisionOutput(
            message_id=inputs.context.message_id,
            action="notify",
            message_type="urgent",
            fired_gate="safety_relevant_media",
            matched_signals=("missing_person_media",),
        )

    if inputs.personalization.group_muted and not inputs.features.mentions_recipient:
        return DecisionOutput(
            message_id=inputs.context.message_id,
            action="mute",
            message_type="spam" if inputs.features.has_forward_or_chain_language else "unknown",
            fired_gate="muted_without_direct_signal",
            matched_signals=("group_muted",),
        )

    if inputs.personalization.group_muted and inputs.features.mentions_recipient:
        if inputs.content_judgment is None:
            raise DecisionInputError("muted mention requires content_judgment")
        label = inputs.content_judgment.label
        if label == "genuine_urgency":
            action, message_type = "notify", "urgent"
        elif label == "generic_forward":
            action, message_type = "mute", "forward"
        else:
            action, message_type = "digest", "unknown"
        return DecisionOutput(
            message_id=inputs.context.message_id,
            action=action,
            message_type=message_type,
            fired_gate="muted_with_mention",
            matched_signals=("group_muted", "recipient_mention", label),
        )

    if inputs.context.conversation_type == "business":
        if inputs.personalization.promotions_opted_out and not inputs.features.transactional_signal:
            return DecisionOutput(
                message_id=inputs.context.message_id,
                action="mute",
                message_type="spam",
                fired_gate="business_opt_out",
                matched_signals=("promotions_opted_out",),
            )
        if inputs.risk.soft_risk_score >= 0.7:
            return DecisionOutput(
                message_id=inputs.context.message_id,
                action="mute",
                message_type="scam",
                fired_gate="business_soft_risk",
                matched_signals=("soft_risk_score",),
            )
        if inputs.features.transactional_signal:
            action = "notify" if inputs.features.has_urgent_language or inputs.features.has_payment_language else "digest"
            message_type = "business_update"
        elif inputs.personalization.trusted_business_relationship:
            action = "notify" if inputs.personalization.recent_engagement_score >= 0.5 else "digest"
            message_type = "business_update" if action == "notify" else "promotion"
        else:
            action = "mute" if inputs.personalization.recent_engagement_score < 0.2 else "digest"
            message_type = "promotion"
        return DecisionOutput(
            message_id=inputs.context.message_id,
            action=action,
            message_type=message_type,
            fired_gate="business_message",
            matched_signals=("business_context",),
        )

    if inputs.personalization.quiet_hours_active and not inputs.features.has_urgent_language:
        return DecisionOutput(
            message_id=inputs.context.message_id,
            action="digest",
            message_type="personal" if inputs.context.conversation_type == "personal" else "unknown",
            fired_gate="quiet_hours",
            matched_signals=("quiet_hours_active",),
        )

    content = (inputs.features.content_text or "").lower()
    explicitly_nonurgent = any(phrase in content for phrase in ("no rush", "nothing urgent", "no urgency", "nothing blocking", "not urgent"))
    if explicitly_nonurgent:
        return DecisionOutput(
            message_id=inputs.context.message_id,
            action="digest",
            message_type=_ordinary_message_type(inputs),
            fired_gate="explicit_non_urgency",
            matched_signals=("explicit_non_urgency",),
        )

    admin_payment = bool(
        inputs.context.conversation_type == "group"
        and inputs.context.group_membership
        and inputs.context.group_membership.get("role") == "admin"
        and inputs.features.has_payment_language
    )
    if (inputs.features.explicit_safe_payment or admin_payment) and inputs.context.conversation_type == "group":
        return DecisionOutput(
            message_id=inputs.context.message_id,
            action="notify",
            message_type="payment",
            fired_gate="safe_payment_admin_message",
            matched_signals=("payment_context", "explicit_safe_payment" if inputs.features.explicit_safe_payment else "trusted_admin"),
        )

    return DecisionOutput(
        message_id=inputs.context.message_id,
        action="notify" if inputs.features.has_urgent_language else "digest",
        message_type=_ordinary_message_type(inputs),
        fired_gate="default_direct_message" if inputs.features.has_urgent_language else "default_digest",
        matched_signals=("urgent" if inputs.features.has_urgent_language else "non_urgent_default",),
    )
