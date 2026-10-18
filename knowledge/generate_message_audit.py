"""Build semantic audit notes for every fixed target message; never writes labels."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from code.knowledge import SemanticKnowledge


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    knowledge = SemanticKnowledge(repo)
    rows = []
    with (repo / "dataset" / "messages.csv").open(encoding="utf-8", newline="") as handle:
        for message in csv.DictReader(handle):
            facts = knowledge.enrich(message.get("media_id"), message.get("message_text"))
            rows.append({
                "message_id": message["message_id"],
                "known_ambiguity": ["media/text contradiction"] if facts["media_conflict"] else [],
                "media_conflict": facts["media_conflict"],
                "expected_reasoning": "; ".join(facts["tags"]) or "text-only semantic review",
                "retrieval_notes": "Use recipient-scoped history; prefer same sender/business/topic and interaction outcomes.",
                "personalization_notes": "Check group mute, sender/business relationship, quiet hours, notification load, and dismissal history.",
                "regression_importance": "high" if facts["sensitive_request"] or "missing_person" in facts["tags"] else "normal",
            })
    (repo / "knowledge" / "message_audit.json").write_text(json.dumps({"messages": rows}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
