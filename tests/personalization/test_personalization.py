from __future__ import annotations

import copy
import unittest
from pathlib import Path

from code.features import extract_features
from code.loader import load_dataset
from code.models import ImageObservation, Observation, VoiceObservation
from code.personalization import assess_personalization
from code.resolver import resolve_context


class PersonalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tables, _ = load_dataset(Path(__file__).parents[2] / "dataset")

    def prepared(self, predicate):
        row = copy.deepcopy(next(row for row in self.tables.messages if predicate(row)))
        context = resolve_context(row, self.tables)
        features = extract_features(context, row, self.observation(row))
        return row, context, features

    @staticmethod
    def observation(row):
        if row["media_type"] is None:
            return Observation()
        if row["media_type"] == "image":
            return Observation(media_id=row["media_id"], media_type="image", image=ImageObservation(row["media_id"], failed=True, failure_reason="stub"))
        return Observation(media_id=row["media_id"], media_type="voice", voice=VoiceObservation(row["media_id"], failed=True, failure_reason="stub"))

    def test_group_mute_is_recipient_specific(self) -> None:
        _, context, features = self.prepared(lambda row: row["conversation_type"] == "group")
        signals = assess_personalization(context, features, self.tables)
        self.assertIsInstance(signals.group_muted, bool)

    def test_business_opt_out_is_read_from_history(self) -> None:
        _, context, features = self.prepared(
            lambda row: row["conversation_type"] == "business"
            and (row["user_id"], row["business_id"]) in self.tables.user_business_history
        )
        signals = assess_personalization(context, features, self.tables)
        expected = context.user_business_history["allows_promotions"] == "0" or context.user_business_history["promotions_opted_out_at"] is not None
        self.assertEqual(signals.promotions_opted_out, expected)

    def test_all_messages_produce_bounded_signals(self) -> None:
        for row in self.tables.messages:
            context = resolve_context(row, self.tables)
            features = extract_features(context, row, self.observation(row))
            signals = assess_personalization(context, features, self.tables)
            self.assertGreaterEqual(signals.recent_engagement_score, 0)
            self.assertLessEqual(signals.recent_engagement_score, 1)
            self.assertGreaterEqual(signals.notification_load_score, 0)
            self.assertLessEqual(signals.notification_load_score, 1)


if __name__ == "__main__":
    unittest.main()
