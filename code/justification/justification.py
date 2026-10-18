"""Deterministic reasons and confidence derived from locked decisions."""

from __future__ import annotations

from ..models import DecisionOutput, EvidenceReference, Justification


class JustificationError(ValueError):
    """A decision cannot be justified under the output contract."""


class JustificationConsistencyError(JustificationError):
    """A justification contradicts its locked decision."""


def _confidence(gate: str) -> float:
    if gate == "hard_safety_override":
        return 0.90
    if gate == "muted_with_mention":
        return 0.80
    if gate in {"business_opt_out", "business_soft_risk"}:
        return 0.87
    if gate == "safety_relevant_media":
        return 0.92
    if gate == "safe_payment_admin_message":
        return 0.88
    if gate in {"explicit_non_urgency", "default_digest"}:
        return 0.78
    return 0.85


def _reason(decision: DecisionOutput, evidence: tuple[EvidenceReference, ...]) -> str:
    reasons = {
        "hard_safety_override": "A deterministic safety rule identified risky or instruction-like content, so the message is muted.",
        "muted_without_direct_signal": "The recipient has muted this group and the message contains no direct signal to the recipient.",
        "muted_with_mention": "The message was evaluated as a direct mention inside a muted group.",
        "business_opt_out": "The recipient has opted out of promotions from this business.",
        "business_soft_risk": "The business message crossed the deterministic soft-risk threshold.",
        "business_message": "The business message was routed using the recipient's stored relationship and engagement signals.",
        "safety_relevant_media": "The attached media contains a safety-relevant missing-person notice, so it is surfaced immediately.",
        "safe_payment_admin_message": "The message is a payment-related administrative update and explicitly warns against unsafe payment links.",
        "explicit_non_urgency": "The sender explicitly says the matter is not urgent, so it can wait for the digest.",
        "default_digest": "The message has no verified urgency or safety signal and is suitable for the digest.",
        "quiet_hours": "The message is non-urgent and arrived during the recipient's quiet hours.",
        "default_direct_message": "The direct message has no stronger suppression or safety signal and is routed for attention.",
    }
    reason = reasons.get(decision.fired_gate, "The message was routed by the deterministic decision engine.")
    signals = ", ".join(decision.matched_signals)
    if signals:
        reason = f"{reason} Matched signals: {signals}."
    if evidence:
        cited = ";".join(reference.message_id for reference in evidence[:2])
        reason = f"{reason} Supporting history: {cited}."
    return reason


def audit_justification(decision: DecisionOutput, justification: Justification) -> None:
    if not justification.reason.strip():
        raise JustificationConsistencyError("reason must be non-empty")
    if not 0 <= justification.confidence <= 1:
        raise JustificationConsistencyError("confidence must be between 0 and 1")
    if decision.fired_gate == "hard_safety_override" and decision.action != "mute":
        raise JustificationConsistencyError("hard safety override must be muted")


def justify(decision: DecisionOutput, evidence: tuple[EvidenceReference, ...]) -> Justification:
    """Create and validate a justification without changing the decision."""
    evidence_ids = tuple(reference.message_id for reference in evidence)
    result = Justification(_reason(decision, evidence), _confidence(decision.fired_gate), evidence_ids)
    audit_justification(decision, result)
    return result
