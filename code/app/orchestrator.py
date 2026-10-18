"""Batch orchestration with typed provider degradation and row isolation."""

from __future__ import annotations

from pathlib import Path

from ..content_judgment import judge_content
from ..decision import decide
from ..features import extract_features
from ..justification import justify
from ..loader import load_dataset
from ..models import BatchReport, DecisionInput, OutputRow, RuntimeConfig
from ..output import build_output_row, validate_output, write_output
from ..perception import perceive
from ..personalization import assess_personalization
from ..resolver import resolve_context
from ..retrieval import retrieve_evidence
from ..risk import assess_risk
from ..utils.gemini_provider import gemini_provider_pool_from_environment
from ..utils.provider_manager import ProviderConfig, ProviderManager, StubProvider


class ProviderStartupError(RuntimeError):
    """No configured Gemini key passed the one-check-per-key startup gate."""


def _provider_manager(runtime: RuntimeConfig) -> ProviderManager:
    cache_root = runtime.perception_cache_path or runtime.judgment_cache_path or Path("cache")
    if runtime.provider_mode == "real":
        try:
            providers = gemini_provider_pool_from_environment()
        except ValueError as exc:
            raise ProviderStartupError(str(exc)) from exc
        return ProviderManager(
            ProviderConfig(
                mode="real",
                provider_name="gemini",
                model="gemini-2.5-flash",
                max_retries=runtime.max_provider_retries,
                cache_root=cache_root,
            ),
            providers,
        )
    return ProviderManager(
        ProviderConfig(
            mode=runtime.provider_mode,
            provider_name="stub",
            model="stub-v1",
            max_retries=runtime.max_provider_retries,
            cache_root=cache_root,
        ),
        {"stub": StubProvider()},
    )


def _degraded_row(message_id: str, reason: str) -> OutputRow:
    return OutputRow(
        message_id,
        "mute",
        "unknown",
        f"Processing degraded for this row: {reason or 'unknown failure'}.",
        0.50,
        "none",
    )


def run_batch(dataset_dir: Path, output_path: Path, runtime: RuntimeConfig) -> BatchReport:
    providers = _provider_manager(runtime)
    if runtime.provider_mode == "real":
        startup = providers.startup_health_check()
        if not startup.healthy:
            categories = ", ".join(f"{index}:{category}" for index, category in startup.failures)
            raise ProviderStartupError(
                f"Gemini startup failed for all {startup.tested_key_count} configured keys; failure categories: {categories or 'unknown'}"
            )
    tables, media_catalog = load_dataset(dataset_dir)
    rows: list[OutputRow] = []
    degraded_count = 0
    retrieval_usage = 0
    risk_usage = 0
    content_judgment_usage = 0

    for message in tables.messages:
        message_id = str(message.get("message_id", "unknown"))
        row_degraded = False
        try:
            context = resolve_context(message, tables)
            observation = perceive(message, media_catalog, providers)
            row_degraded = bool(
                (observation.image and observation.image.failed)
                or (observation.voice and observation.voice.failed)
            )
            features = extract_features(context, message, observation)
            personalization = assess_personalization(context, features, tables)
            evidence = retrieve_evidence(context, features, tables)
            retrieval_usage += bool(evidence)
            risk = assess_risk(
                context,
                features,
                observation,
                evidence,
                personalization.notification_load_score,
            )
            risk_usage += 1
            content_judgment = None
            if (
                personalization.group_muted
                and features.mentions_recipient
                and not risk.hard_override
            ):
                content_judgment = judge_content(context, features, observation, providers)
                content_judgment_usage += 1
                row_degraded = row_degraded or content_judgment.source == "fallback"
            decision = decide(
                DecisionInput(context, features, risk, personalization, content_judgment, evidence)
            )
            rows.append(build_output_row(decision, justify(decision, evidence)))
        except Exception as exc:
            if runtime.fail_fast_on_configuration_error and isinstance(exc, (ValueError, OSError)) and message_id == "unknown":
                raise
            rows.append(_degraded_row(message_id, str(exc)))
            row_degraded = True
        degraded_count += int(row_degraded)

    target_ids = [message["message_id"] for message in tables.messages]
    validate_output(rows, target_ids)
    write_output(rows, output_path)
    return BatchReport(
        target_count=len(target_ids),
        output_count=len(rows),
        degraded_count=degraded_count,
        provider_call_count=providers.provider_call_count,
        cache_hit_count=providers.cache_hit_count,
        output_path=output_path,
        validation_passed=True,
        cache_miss_count=providers.cache_miss_count,
        provider_skip_count=providers.provider_skip_count,
        retrieval_usage=int(retrieval_usage),
        risk_usage=risk_usage,
        content_judgment_usage=content_judgment_usage,
        provider_call_counts=dict(providers.provider_call_counts),
        provider_call_log=tuple(providers.provider_call_log),
    )
