"""Shared data contracts.

This module owns representation and validation of cross-module values only.
It intentionally contains no routing, lookup, provider, or serialization logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

Action = Literal["notify", "digest", "mute"]
MessageType = Literal[
    "personal",
    "urgent",
    "event",
    "payment",
    "business_update",
    "promotion",
    "greeting",
    "forward",
    "spam",
    "scam",
    "unknown",
]
MediaType = Literal["image", "voice"]
ContentLabel = Literal["genuine_urgency", "generic_forward", "ambiguous"]
JudgmentSource = Literal["provider", "fallback", "deterministic"]
ProviderMode = Literal["real", "stub", "fallback"]


def _bounded_score(value: float, field_name: str) -> float:
    if not 0 <= value <= 1:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return float(value)


@dataclass(frozen=True)
class DatasetTables:
    messages: Sequence[Mapping[str, Any]]
    sample_messages: Sequence[Mapping[str, Any]]
    users: Mapping[str, Mapping[str, Any]]
    groups: Mapping[str, Mapping[str, Any]]
    group_members: Mapping[tuple[str, str], Mapping[str, Any]]
    business_accounts: Mapping[str, Mapping[str, Any]]
    user_business_history: Mapping[tuple[str, str], Mapping[str, Any]]
    message_history: Mapping[str, Mapping[str, Any]]
    message_events: Mapping[tuple[str, str], Mapping[str, Any]]
    daily_notification_summary: Mapping[tuple[str, str], Mapping[str, Any]]


@dataclass(frozen=True)
class MediaCatalog:
    images: Mapping[str, Path]
    voice_notes: Mapping[str, Path]


@dataclass(frozen=True)
class ImageObservation:
    media_id: str
    ocr_text: str | None = None
    confidence: float | None = None
    failed: bool = False
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.media_id:
            raise ValueError("media_id must be non-empty")
        if self.confidence is not None:
            _bounded_score(self.confidence, "confidence")
        if self.failed and not self.failure_reason:
            raise ValueError("failed image observations require failure_reason")
        if self.failed and self.ocr_text is not None:
            raise ValueError("failed image observations cannot contain ocr_text")


@dataclass(frozen=True)
class VoiceObservation:
    media_id: str
    transcript: str | None = None
    confidence: float | None = None
    failed: bool = False
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.media_id:
            raise ValueError("media_id must be non-empty")
        if self.confidence is not None:
            _bounded_score(self.confidence, "confidence")
        if self.failed and not self.failure_reason:
            raise ValueError("failed voice observations require failure_reason")
        if self.failed and self.transcript is not None:
            raise ValueError("failed voice observations cannot contain transcript")


@dataclass(frozen=True)
class Observation:
    media_id: str | None = None
    media_type: MediaType | None = None
    image: ImageObservation | None = None
    voice: VoiceObservation | None = None

    def __post_init__(self) -> None:
        nested = (self.image is not None) + (self.voice is not None)
        if self.media_type is None:
            if self.media_id is not None or nested:
                raise ValueError("text observations cannot contain media data")
            return
        if self.media_type not in ("image", "voice"):
            raise ValueError("unsupported media_type")
        if self.media_id is None or nested != 1:
            raise ValueError("media observations require exactly one matching nested result")
        if self.media_type == "image" and self.image is None:
            raise ValueError("image observations require image data")
        if self.media_type == "voice" and self.voice is None:
            raise ValueError("voice observations require voice data")
        nested_observation = self.image or self.voice
        if nested_observation is None or nested_observation.media_id != self.media_id:
            raise ValueError("nested media_id must match observation media_id")


@dataclass(frozen=True)
class ResolvedContext:
    message_id: str
    user_id: str
    conversation_type: Literal["personal", "group", "business"]
    created_at: datetime
    group_id: str | None
    business_id: str | None
    sender_user_id: str | None
    user: Mapping[str, Any]
    sender: Mapping[str, Any] | None = None
    group: Mapping[str, Any] | None = None
    group_membership: Mapping[str, Any] | None = None
    business: Mapping[str, Any] | None = None
    user_business_history: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class MessageFeatures:
    message_id: str
    message_text: str | None
    media_type: MediaType | None
    media_id: str | None
    forwarded_count: int
    content_text: str | None = None
    content_language: str | None = None
    mentions_recipient: bool = False
    has_url: bool = False
    has_payment_language: bool = False
    has_otp_or_verification_language: bool = False
    has_forward_or_chain_language: bool = False
    has_urgent_language: bool = False
    semantic_tags: tuple[str, ...] = ()
    transactional_signal: bool = False
    promotional_signal: bool = False
    sensitive_request: bool = False
    payment_request: bool = False
    explicit_safe_payment: bool = False
    media_conflict: bool = False

    def __post_init__(self) -> None:
        if not self.message_id:
            raise ValueError("message_id must be non-empty")
        if self.forwarded_count < 0:
            raise ValueError("forwarded_count cannot be negative")
        if (self.media_type is None) != (self.media_id is None):
            raise ValueError("media_type and media_id must be present together")


@dataclass(frozen=True)
class EvidenceReference:
    message_id: str
    user_id: str
    relevance_reason: str
    relevance_score: float

    def __post_init__(self) -> None:
        if not self.message_id or not self.user_id or not self.relevance_reason:
            raise ValueError("evidence fields must be non-empty")
        _bounded_score(self.relevance_score, "relevance_score")


@dataclass(frozen=True)
class RiskSignals:
    hard_override: bool
    matched_rules: tuple[str, ...]
    soft_risk_score: float
    is_scam_like: bool
    is_spam_like: bool

    def __post_init__(self) -> None:
        _bounded_score(self.soft_risk_score, "soft_risk_score")
        if self.hard_override and not self.matched_rules:
            raise ValueError("hard overrides require matched rules")


@dataclass(frozen=True)
class PersonalizationSignals:
    group_muted: bool
    promotions_opted_out: bool
    quiet_hours_active: bool
    recent_engagement_score: float
    notification_load_score: float
    trusted_business_relationship: bool
    dismissal_signal: bool

    def __post_init__(self) -> None:
        _bounded_score(self.recent_engagement_score, "recent_engagement_score")
        _bounded_score(self.notification_load_score, "notification_load_score")


@dataclass(frozen=True)
class ContentJudgment:
    label: ContentLabel
    confidence: float
    source: JudgmentSource
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        _bounded_score(self.confidence, "confidence")
        if self.source == "fallback" and self.label != "ambiguous":
            raise ValueError("fallback judgments must be ambiguous")
        if self.source == "fallback" and not self.failure_reason:
            raise ValueError("fallback judgments require failure_reason")


@dataclass(frozen=True)
class DecisionInput:
    context: ResolvedContext
    features: MessageFeatures
    risk: RiskSignals
    personalization: PersonalizationSignals
    content_judgment: ContentJudgment | None
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        if self.context.message_id != self.features.message_id:
            raise ValueError("context and features must refer to the same message")
        for evidence in self.evidence:
            if evidence.user_id != self.context.user_id:
                raise ValueError("evidence must belong to the resolved user")


@dataclass(frozen=True)
class DecisionOutput:
    message_id: str
    action: Action
    message_type: MessageType
    fired_gate: str
    matched_signals: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.message_id or not self.fired_gate:
            raise ValueError("decision message_id and fired_gate must be non-empty")
        if self.action not in ("notify", "digest", "mute"):
            raise ValueError("unsupported action")
        if self.message_type not in ("personal", "urgent", "event", "payment", "business_update", "promotion", "greeting", "forward", "spam", "scam", "unknown"):
            raise ValueError("unsupported message_type")


@dataclass(frozen=True)
class Justification:
    reason: str
    confidence: float
    evidence_message_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("reason must be non-empty")
        _bounded_score(self.confidence, "confidence")


@dataclass(frozen=True)
class OutputRow:
    message_id: str
    action: Action
    message_type: MessageType
    reason: str
    confidence: float
    evidence_message_ids: str

    def __post_init__(self) -> None:
        if not self.message_id or not self.reason.strip():
            raise ValueError("output message_id and reason must be non-empty")
        _bounded_score(self.confidence, "confidence")
        if not self.evidence_message_ids:
            raise ValueError("evidence_message_ids must be non-empty or 'none'")
        if self.evidence_message_ids != "none" and any(not value for value in self.evidence_message_ids.split(";")):
            raise ValueError("evidence_message_ids must contain non-empty IDs")


@dataclass(frozen=True)
class RuntimeConfig:
    provider_mode: ProviderMode
    perception_cache_path: Path | None
    judgment_cache_path: Path | None
    max_provider_retries: int
    fail_fast_on_configuration_error: bool

    def __post_init__(self) -> None:
        if self.max_provider_retries < 0:
            raise ValueError("max_provider_retries cannot be negative")


@dataclass(frozen=True)
class BatchReport:
    target_count: int
    output_count: int
    degraded_count: int
    provider_call_count: int
    cache_hit_count: int
    output_path: Path
    validation_passed: bool
    cache_miss_count: int = 0
    provider_skip_count: int = 0
    retrieval_usage: int = 0
    risk_usage: int = 0
    content_judgment_usage: int = 0
    provider_call_counts: Mapping[int, int] = field(default_factory=dict)
    provider_call_log: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        counts = (
            self.target_count,
            self.output_count,
            self.degraded_count,
            self.provider_call_count,
            self.cache_hit_count,
            self.cache_miss_count,
            self.provider_skip_count,
            self.retrieval_usage,
            self.risk_usage,
            self.content_judgment_usage,
        )
        if any(count < 0 for count in counts):
            raise ValueError("batch counts cannot be negative")
