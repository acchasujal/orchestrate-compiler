from __future__ import annotations

import copy
import unittest
from pathlib import Path

from code.features import extract_features
from code.loader import load_dataset
from code.models import ImageObservation, Observation, VoiceObservation
from code.resolver import resolve_context


class FeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tables, _ = load_dataset(Path(__file__).parents[2] / "dataset")
        cls.messages = list(cls.tables.messages)

    def test_direct_text_features_are_deterministic(self) -> None:
        row = copy.deepcopy(next(row for row in self.messages if row["message_id"] == "msg_040"))
        context = resolve_context(row, self.tables)
        features = extract_features(context, row, Observation())
        self.assertTrue(features.mentions_recipient)
        self.assertTrue(features.has_forward_or_chain_language)
        self.assertEqual(features.forwarded_count, 7)

    def test_text_without_media_uses_empty_observation(self) -> None:
        row = copy.deepcopy(next(row for row in self.messages if row["media_type"] is None))
        context = resolve_context(row, self.tables)
        features = extract_features(context, row, Observation())
        self.assertEqual(features.media_type, None)

    def test_all_target_rows_produce_features(self) -> None:
        for row in self.messages:
            context = resolve_context(row, self.tables)
            if row["media_type"] is None:
                observation = Observation()
            elif row["media_type"] == "image":
                observation = Observation(
                    media_id=row["media_id"],
                    media_type="image",
                    image=ImageObservation(row["media_id"], failed=True, failure_reason="stub"),
                )
            else:
                observation = Observation(
                    media_id=row["media_id"],
                    media_type="voice",
                    voice=VoiceObservation(row["media_id"], failed=True, failure_reason="stub"),
                )
            extract_features(context, row, observation)
