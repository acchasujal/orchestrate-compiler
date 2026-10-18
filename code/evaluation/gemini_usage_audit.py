"""Render a provider-call audit without exposing credentials."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


def render_usage_audit(batch_report: Any, report_path: Path) -> dict[str, Any]:
    calls = list(getattr(batch_report, "provider_call_log", ()))
    necessity = (
        "Live Gemini calls were made only when media content required OCR/ASR perception or gated semantic content judgment, and deterministic logic could not resolve the row."
        if calls
        else "Offline fallback run made no Gemini calls; mocked provider tests are not live Gemini usage."
    )
    result = {
        "total_calls": len(calls),
        "calls": calls,
        "provider_call_counts": dict(getattr(batch_report, "provider_call_counts", {})),
        "cache_hits": getattr(batch_report, "cache_hit_count", 0),
        "cache_misses": getattr(batch_report, "cache_miss_count", 0),
        "provider_skips": getattr(batch_report, "provider_skip_count", 0),
        "necessary_assessment": necessity,
    }
    lines = ["# Gemini Usage Audit", "", f"- Total Gemini calls: `{result['total_calls']}`", f"- Cache hits: `{result['cache_hits']}`", f"- Cache misses: `{result['cache_misses']}`", f"- Provider skips: `{result['provider_skips']}`", ""]
    if calls:
        lines.append("## Calls")
        for index, call in enumerate(calls, start=1):
            lines.append(f"{index}. key index `{call.get('key_index')}`, operation `{call.get('operation')}`, namespace `{call.get('namespace')}`, SHA256 `{call.get('request_hash')}`")
    else:
        lines.append("No live Gemini calls occurred in the offline validation run.")
    lines.extend(["", f"- Necessity assessment: {result['necessary_assessment']}"])
    Path(report_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
