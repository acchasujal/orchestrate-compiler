"""Gated semantic interpretation; never emits a routing action."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from ..models import ContentJudgment, MessageFeatures, Observation, ResolvedContext


class JudgmentClient(Protocol):
    config: Any

    def execute(self, request: Mapping[str, Any], media_bytes: bytes = b"", namespace: str = "judgment") -> Any: ...

    def skip(self) -> None: ...


def _deterministic_judgment(features: MessageFeatures) -> ContentJudgment | None:
    """Resolve unambiguous muted-mention classes without a provider."""
    if features.has_forward_or_chain_language and features.forwarded_count > 0:
        return ContentJudgment("generic_forward", 0.98, "deterministic")
    content = (features.content_text or "").lower()
    direct_urgency = any(term in content for term in (
        "doctor appointment", "clinic called", "confirm if you can leave", "call immediately", "need you now"
    ))
    if features.has_urgent_language and direct_urgency:
        return ContentJudgment("genuine_urgency", 0.95, "deterministic")
    return None


def judge_content(context: ResolvedContext, features: MessageFeatures, observation: Observation | None, client: JudgmentClient) -> ContentJudgment:
    deterministic = _deterministic_judgment(features)
    if deterministic is not None:
        return deterministic
    if getattr(client.config, "mode", "real") != "real":
        client.skip()
        return ContentJudgment("ambiguous", 0.0, "fallback", "content judgment provider is not enabled")
    prompt = (
        "Interpret message semantics only. Return genuine_urgency when the mention contains a real time-sensitive personal matter; "
        "generic_forward for chain/forward content; otherwise ambiguous. Never output a routing action.\n"
        f"Recipient conversation type: {context.conversation_type}\nMessage content: {features.content_text or '[unavailable]'}\n"
        f"Forwarded count: {features.forwarded_count}; has urgent language: {features.has_urgent_language}"
    )
    result = client.execute({"operation": "content_judgment", "prompt": prompt}, namespace="judgment/content")
    if not isinstance(result, Mapping) or result.get("status") == "degraded":
        reason = str(result.get("reason", "provider degraded")) if isinstance(result, Mapping) else "invalid provider response"
        return ContentJudgment("ambiguous", 0.0, "fallback", reason)
    label = result.get("label")
    try:
        confidence = float(result.get("confidence", 0.0))
        if label not in {"genuine_urgency", "generic_forward", "ambiguous"}:
            raise ValueError("unsupported semantic label")
        return ContentJudgment(label, max(0.0, min(1.0, confidence)), "provider")
    except (TypeError, ValueError) as exc:
        return ContentJudgment("ambiguous", 0.0, "fallback", f"invalid provider judgment: {exc}")
