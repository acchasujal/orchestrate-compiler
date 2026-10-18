"""Fixed-dataset semantic facts, kept separate from routing labels."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping


class SemanticKnowledge:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.media = self._read("media_analysis.json")
        self.voice = self._read("voice_analysis.json")
        self.business = self._read("business_rules.json")

    def _read(self, name: str) -> dict[str, Any]:
        path = self.root / "knowledge" / name
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def media_tags(self, media_id: str | None) -> set[str]:
        if not media_id:
            return set()
        record = self.media.get(media_id, {})
        return set(record.get("tags", []))

    def media_summary(self, media_id: str | None) -> str | None:
        if not media_id:
            return None
        return self.media.get(media_id, {}).get("summary")

    def voice_record(self, media_id: str | None) -> Mapping[str, Any]:
        return self.voice.get(media_id or "", {})

    def business_terms(self, kind: str) -> tuple[str, ...]:
        return tuple(self.business.get(f"{kind}_terms", ()))

    def enrich(self, media_id: str | None, text: str | None) -> dict[str, Any]:
        content = str(text or "")
        tags = self.media_tags(media_id)
        voice = self.voice_record(media_id)
        if voice.get("category") not in (None, "unknown"):
            tags.add(str(voice["category"]))
        if voice.get("urgency") == "high":
            tags.add("urgent")
        lower = content.lower()
        transactional = bool(tags & {"transaction", "business_update"}) or any(term in lower for term in self.business_terms("transactional"))
        promotional = bool(tags & {"promotion"}) or any(term in lower for term in self.business_terms("promotional"))
        # Prize/lottery scam: 'selected for reward', 'claim your prize', etc.
        _prize_scam = bool(re.search(
            r"selected\s+(?:for|as)\s+(?:reward|prize|winner|gift)|you\s+(?:have\s+)?won\s+(?:a\s+)?(?:prize|reward|voucher|gift|cash)|claim\s+(?:your\s+)?(?:reward|prize|voucher|gift|cash|amount)\b",
            lower,
        ))
        sensitive = bool(re.search(
            r"(?:\botp\b|one[- ]time|verification\s+code|login\s+code|wallet\s+pin|account\s+number|send\s+the\s+code|share\s+otp|code\s+(?:daal|batao)|account.{0,30}(?:block|hold|restrict)|profile.{0,30}(?:block|hold|restrict)|complete\s+(?:pending|account)\s+(?:check|verify|verification)|pending\s+account\s+(?:check|verify|verification))",
            lower,
        )) and not bool(re.search(r"(?:no|without)\s+(?:payment\s+or\s+)?otp|no\s+(?:payment|verification)\s+(?:or\s+)?otp|otp\s+is\s+not\s+required", lower))
        sensitive = sensitive or _prize_scam
        payment_request = bool(re.search(
            r"(?:pay\s+(?:processing\s+)?fee|scan\s+and\s+pay|scan.{0,20}(?:qr|code).{0,20}pay|send\s+screenshot|payment\s+link|pay\s+rs\.?|token\s+today|confirm\s+your\s+wallet|(?:confirm|verify).{0,20}wallet|wallet.{0,20}(?:detail|card|verify)|share\s+(?:your\s+)?account\s+number)",
            lower,
        ))
        explicit_safe_payment = bool(re.search(r"(?:do not|don't|never)\s+(?:use|click)\s+(?:any\s+)?payment\s+link", lower))
        contradiction = bool(media_id and text and tags and (
            ("missing_person" in tags and not re.search(r"missing|lost|found|help|contact", lower))
            or ("promotion" in tags and re.search(r"otp|wallet|refund|verification", lower))
        ))
        return {
            "tags": tuple(sorted(tags)),
            "transactional": transactional,
            "promotional": promotional,
            "sensitive_request": sensitive or voice.get("category") == "scam",
            "payment_request": payment_request and not explicit_safe_payment,
            "explicit_safe_payment": explicit_safe_payment,
            "media_conflict": contradiction,
            "voice_summary": voice.get("summary"),
        }
