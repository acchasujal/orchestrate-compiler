from __future__ import annotations

import unittest
from datetime import datetime

from code.decision import DecisionInputError, decide
from code.models import (
    ContentJudgment,
    DecisionInput,
    MessageFeatures,
    PersonalizationSignals,
    ResolvedContext,
    RiskSignals,
)


def make_input(**overrides: object) -> DecisionInput:
    context = ResolvedContext("m", "u", "personal", datetime(2026, 1, 1), None, None, "s", {}, {})
    features = MessageFeatures("m", "hello", None, None, 0)
    risk = RiskSignals(False, (), 0.0, False, False)
    personalization = PersonalizationSignals(False, False, False, 0.0, 0.0, False, False)
    values = dict(context=context, features=features, risk=risk, personalization=personalization, content_judgment=None, evidence=())
    values.update(overrides)
    return DecisionInput(**values)


class DecisionTests(unittest.TestCase):
    def test_hard_safety_override_is_terminal(self) -> None:
        result = decide(make_input(risk=RiskSignals(True, ("domain_mismatch",), 0.1, True, False)))
        self.assertEqual((result.action, result.message_type, result.fired_gate), ("mute", "scam", "hard_safety_override"))

    def test_muted_without_mention_mutes(self) -> None:
        p = PersonalizationSignals(True, False, False, 0.0, 0.0, False, False)
        self.assertEqual(decide(make_input(personalization=p)).action, "mute")

    def test_muted_mention_requires_content_judgment(self) -> None:
        p = PersonalizationSignals(True, False, False, 0.0, 0.0, False, False)
        f = MessageFeatures("m", "@u urgent", None, None, 0, mentions_recipient=True, has_urgent_language=True)
        with self.assertRaises(DecisionInputError):
            decide(make_input(personalization=p, features=f))

    def test_muted_mention_content_labels(self) -> None:
        p = PersonalizationSignals(True, False, False, 0.0, 0.0, False, False)
        f = MessageFeatures("m", "@u", None, None, 0, mentions_recipient=True)
        for label, expected in (("genuine_urgency", "notify"), ("generic_forward", "mute"), ("ambiguous", "digest")):
            result = decide(make_input(personalization=p, features=f, content_judgment=ContentJudgment(label, 0.8, "provider")))
            self.assertEqual(result.action, expected)

    def test_business_opt_out_precedes_soft_risk(self) -> None:
        context = ResolvedContext("m", "u", "business", datetime(2026, 1, 1), None, "b", None, {}, None, None, {}, {})
        p = PersonalizationSignals(False, True, False, 0.0, 0.0, False, False)
        r = RiskSignals(False, (), 0.9, True, False)
        result = decide(make_input(context=context, personalization=p, risk=r))
        self.assertEqual((result.action, result.fired_gate), ("mute", "business_opt_out"))

    def test_quiet_hours_digest_non_urgent(self) -> None:
        p = PersonalizationSignals(False, False, True, 0.0, 0.0, False, False)
        self.assertEqual(decide(make_input(personalization=p)).action, "digest")

    def test_default_nonurgent_messages_digest(self) -> None:
        self.assertEqual(decide(make_input()).action, "digest")


if __name__ == "__main__":
    unittest.main()
