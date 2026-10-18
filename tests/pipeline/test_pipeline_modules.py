from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from code.app.orchestrator import run_batch
from code.content_judgment import judge_content
from code.decision import decide
from code.features import extract_features
from code.loader import load_dataset
from code.models import DecisionInput, Observation, PersonalizationSignals, RiskSignals, RuntimeConfig
from code.perception import perceive
from code.personalization import assess_personalization
from code.resolver import resolve_context
from code.retrieval import retrieve_evidence


class PipelineTests(unittest.TestCase):
    repo = Path(__file__).parents[2]

    def test_stub_pipeline_is_complete_and_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output.csv"
            report = run_batch(
                self.repo / "dataset",
                output,
                RuntimeConfig("stub", Path(directory) / "cache", Path(directory) / "cache", 0, True),
            )
            self.assertEqual(report.target_count, 110)
            self.assertEqual(report.output_count, 110)
            self.assertEqual(report.risk_usage, 110)
            self.assertGreater(report.retrieval_usage, 0)
            self.assertGreater(report.content_judgment_usage, 0)
            self.assertGreater(report.provider_skip_count, 0)

    def test_named_deterministic_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output.csv"
            run_batch(
                self.repo / "dataset",
                output,
                RuntimeConfig("stub", Path(directory) / "cache", Path(directory) / "cache", 0, True),
            )
            with output.open(encoding="utf-8", newline="") as handle:
                rows = {row["message_id"]: row for row in csv.DictReader(handle)}
            self.assertEqual((rows["msg_110"]["action"], rows["msg_110"]["message_type"]), ("mute", "scam"))
            self.assertEqual(rows["msg_021"]["action"], "notify")
            self.assertEqual((rows["msg_022"]["action"], rows["msg_022"]["message_type"]), ("mute", "scam"))
            self.assertEqual(rows["msg_040"]["action"], "mute")
            self.assertEqual(rows["msg_056"]["action"], "notify")

    def test_one_row_failure_does_not_abort_batch(self) -> None:
        original = __import__("code.app.orchestrator", fromlist=["resolve_context"]).resolve_context
        calls = {"count": 0}

        def fail_once(message, tables):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("synthetic row failure")
            return original(message, tables)

        with tempfile.TemporaryDirectory() as directory:
            with patch("code.app.orchestrator.resolve_context", side_effect=fail_once):
                report = run_batch(
                    self.repo / "dataset",
                    Path(directory) / "output.csv",
                    RuntimeConfig("stub", Path(directory) / "cache", Path(directory) / "cache", 0, True),
                )
            self.assertEqual(report.output_count, 110)
            self.assertGreaterEqual(report.degraded_count, 1)

    def test_mocked_ocr_and_asr_are_typed_and_cached_by_manager_boundary(self) -> None:
        tables, media_catalog = load_dataset(self.repo / "dataset")
        image_message = next(row for row in tables.messages if row["media_type"] == "image")
        voice_message = next(row for row in tables.messages if row["media_type"] == "voice")

        class FakeClient:
            config = SimpleNamespace(mode="real")

            def __init__(self):
                self.requests = []

            def execute(self, request, media_bytes=b"", namespace="judgment"):
                self.requests.append((request, media_bytes, namespace))
                return {"text": "extracted media text", "confidence": 0.88}

            def skip(self):
                raise AssertionError("mock provider should not be skipped")

        client = FakeClient()
        image_observation = perceive(image_message, media_catalog, client)
        voice_observation = perceive(voice_message, media_catalog, client)
        self.assertEqual(image_observation.image.ocr_text, "extracted media text")
        self.assertEqual(voice_observation.voice.transcript, "extracted media text")
        self.assertEqual([request[0]["operation"] for request in client.requests], ["perception", "perception"])

    def test_mocked_content_judgment_separates_named_contrast_pair(self) -> None:
        tables, _ = load_dataset(self.repo / "dataset")

        class FakeJudgmentClient:
            config = SimpleNamespace(mode="real")

            def execute(self, request, media_bytes=b"", namespace="judgment"):
                label = "generic_forward" if "blessings" in request["prompt"] else "genuine_urgency"
                return {"label": label, "confidence": 0.8}

            def skip(self):
                raise AssertionError("mock provider should not be skipped")

        client = FakeJudgmentClient()
        results = {}
        for message_id in ("msg_040", "msg_056"):
            row = next(row for row in tables.messages if row["message_id"] == message_id)
            context = resolve_context(row, tables)
            features = extract_features(context, row, Observation())
            judgment = judge_content(context, features, Observation(), client)
            personalization = assess_personalization(context, features, tables)
            decision = decide(DecisionInput(context, features, RiskSignals(False, (), 0.0, False, False), personalization, judgment, retrieve_evidence(context, features, tables)))
            results[message_id] = (judgment.label, decision.action)
        self.assertEqual(results, {"msg_040": ("generic_forward", "mute"), "msg_056": ("genuine_urgency", "notify")})


if __name__ == "__main__":
    unittest.main()
