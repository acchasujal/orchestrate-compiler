"""Deterministic safety and abuse signals."""

from __future__ import annotations

import re

from ..models import EvidenceReference, MessageFeatures, Observation, ResolvedContext, RiskSignals

_INJECTION = re.compile(r"(?:ignore|disregard).{0,40}(?:instruction|previous|sender risk)|assistant instruction|system prompt|system note.{0,80}(?:router|trusted\s+admin|override|mark\s+notify)|notification\s+router.{0,60}(?:trusted|override|mark)", re.I | re.S)
_PAYMENT_LINK = re.compile(r"\b(?:use this link|click|send screenshot|payment link)\b", re.I)
_NEGATED_PAYMENT_LINK = re.compile(r"\b(?:do not|don't|never)\s+(?:use|click)\s+(?:any\s+)?payment link\b", re.I)


def assess_risk(
    context: ResolvedContext,
    features: MessageFeatures,
    observation: Observation | None,
    evidence: tuple[EvidenceReference, ...] = (),
    notification_load_score: float = 0.0,
) -> RiskSignals:
    text = features.content_text or ""
    rules: list[str] = []
    score = 0.0
    scam = False
    spam = False

    business = context.business or {}
    official = (business.get("official_domain") or "").strip().lower()
    used = (business.get("domain_used_by_sender") or "").strip().lower()
    mismatch = bool(official and used and official != used)
    if mismatch:
        rules.append("business_domain_mismatch")
        score += 0.45
        scam = True
    if _INJECTION.search(text):
        rules.append("embedded_instruction")
        score += 0.30
        scam = True
    if features.has_otp_or_verification_language or features.sensitive_request:
        rules.append("sensitive_verification_request")
        score += 0.20
        scam = True
    if features.has_url:
        score += 0.10
    if features.has_payment_language or features.payment_request:
        score += 0.12
    positive_payment_link = bool(_PAYMENT_LINK.search(text) and not _NEGATED_PAYMENT_LINK.search(text))
    if features.payment_request and not features.explicit_safe_payment:
        rules.append("payment_pressure")
        score += 0.35
        scam = True
    if positive_payment_link:
        rules.append("payment_link_request")
        score += 0.35
        scam = True

    history = context.user_business_history or {}
    if history.get("allows_promotions") == "0" or history.get("promotions_opted_out_at") is not None:
        rules.append("promotions_opted_out")
        score += 0.25
        spam = True
    if business and int(business.get("user_reports_30d") or 0) >= 20 and not business.get("verified") == "1":
        rules.append("unverified_business_reports")
        score += 0.20
        scam = True
    if features.forwarded_count >= 5 and features.has_forward_or_chain_language:
        rules.append("high_forwarded_chain")
        score += 0.35
        spam = True

    for reference in evidence:
        event = None
        # Evidence provenance is already recipient-scoped; event lookup is performed by the orchestrator's tables.
        if "reported" in reference.relevance_reason.lower() or "dismiss" in reference.relevance_reason.lower():
            event = True
        if event:
            score += 0.15
            spam = True

    if observation is not None:
        failed = bool((observation.image and observation.image.failed) or (observation.voice and observation.voice.failed))
        if failed:
            score += 0.05
    if notification_load_score >= 0.8:
        rules.append("high_notification_load")
        score += 0.10

    hard = bool(
        mismatch
        or (_INJECTION.search(text) and (features.has_otp_or_verification_language or features.sensitive_request or features.has_url or features.has_payment_language))
        or (features.sensitive_request and not features.explicit_safe_payment)
        or (positive_payment_link and (features.has_payment_language or features.payment_request))
        or (features.payment_request and features.has_urgent_language)
        or (
            features.forwarded_count >= 5
            and features.has_forward_or_chain_language
            and not (
                context.group_membership
                and context.group_membership.get("group_muted_by_user") == "1"
                and features.mentions_recipient
            )
        )
    )
    return RiskSignals(hard, tuple(dict.fromkeys(rules)), min(1.0, score), scam, spam)
