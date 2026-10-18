from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from code.utils.provider_manager import (
    PermanentProviderError,
    ProviderConfig,
    ProviderManager,
    RequestKey,
    StubProvider,
    TransientProviderError,
)


class CountingProvider(StubProvider):
    def __init__(self, failure=None, result=None, healthy=True):
        self.calls = 0
        self.failure = failure
        self.result = result or {"ok": True}
        self.healthy = healthy

    def health_check(self):
        return self.healthy

    def execute(self, request):
        self.calls += 1
        if self.failure:
            raise self.failure
        return self.result


class ProviderTests(unittest.TestCase):
    def test_request_hash_includes_media_bytes_not_filename(self) -> None:
        first = RequestKey("p", "m", "v1", {"text": "x"}, b"bytes").digest()
        second = RequestKey("p", "m", "v1", {"text": "x"}, b"bytes").digest()
        third = RequestKey("p", "m", "v1", {"text": "x"}, b"other").digest()
        self.assertEqual(first, second)
        self.assertNotEqual(first, third)

    def test_success_cache_survives_manager_instances(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = ProviderConfig(cache_root=Path(directory))
            first_provider = CountingProvider()
            first = ProviderManager(config, {"stub": first_provider})
            self.assertEqual(first.execute({"x": 1}, namespace="perception/image"), {"ok": True})
            second_provider = CountingProvider()
            second = ProviderManager(config, {"stub": second_provider})
            self.assertEqual(second.execute({"x": 1}, namespace="perception/image"), {"ok": True})
            self.assertEqual(first_provider.calls, 1)
            self.assertEqual(second_provider.calls, 0)

    def test_permanent_failure_is_cached_without_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            provider = CountingProvider(PermanentProviderError("invalid key"))
            manager = ProviderManager(ProviderConfig(cache_root=Path(directory), max_retries=3), {"stub": provider})
            manager.execute({"x": 2})
            manager.execute({"x": 2})
            self.assertEqual(provider.calls, 1)

    def test_transient_failure_retries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            provider = CountingProvider(TransientProviderError("timeout"))
            manager = ProviderManager(ProviderConfig(cache_root=Path(directory), max_retries=2), {"stub": provider})
            result = manager.execute({"x": 3})
            self.assertEqual(provider.calls, 3)
            self.assertEqual(result["status"], "degraded")

    def test_permanent_failure_rotates_to_next_provider(self) -> None:
        first = CountingProvider(PermanentProviderError("bad key", "invalid_key"))
        second = CountingProvider(result={"provider": 2})
        first.name = "gemini_0"
        second.name = "gemini_1"
        manager = ProviderManager(
            ProviderConfig(provider_name="gemini", cache_root=Path(tempfile.mkdtemp())),
            {"gemini_0": first, "gemini_1": second},
        )
        result = manager.execute({"rotation": True})
        self.assertEqual(result, {"provider": 2})
        self.assertEqual(first.calls, 1)
        self.assertEqual(second.calls, 1)
        self.assertTrue(manager.provider_states[0].permanent_failure)
        self.assertEqual(manager.active_provider_index, 1)

    def test_startup_tests_each_key_once_until_success(self) -> None:
        first = CountingProvider(PermanentProviderError("bad key", "invalid_key"))
        second = CountingProvider(result={"status": "success"})
        first.name = "gemini_0"
        second.name = "gemini_1"
        manager = ProviderManager(
            ProviderConfig(provider_name="gemini", cache_root=Path(tempfile.mkdtemp()), max_retries=5),
            {"gemini_0": first, "gemini_1": second},
        )
        result = manager.startup_health_check()
        self.assertTrue(result.healthy)
        self.assertEqual((result.configured_key_count, result.tested_key_count, result.active_key_index), (2, 2, 1))
        self.assertEqual(first.calls, 1)
        self.assertEqual(second.calls, 1)
        self.assertEqual(manager.provider_call_count, 2)

    def test_configured_provider_name_selects_initial_provider(self) -> None:
        first = CountingProvider(result={"provider": "first"})
        second = CountingProvider(result={"provider": "second"})
        manager = ProviderManager(
            ProviderConfig(provider_name="second", cache_root=Path(tempfile.mkdtemp())),
            {"first": first, "second": second},
        )
        self.assertEqual(manager.execute({"selection": True}), {"provider": "second"})
        self.assertEqual(first.calls, 0)
        self.assertEqual(second.calls, 1)

    def test_unhealthy_provider_degrades_without_call(self) -> None:
        provider = CountingProvider(healthy=False)
        manager = ProviderManager(
            ProviderConfig(provider_name="stub", cache_root=Path(tempfile.mkdtemp())),
            {"stub": provider},
        )
        result = manager.execute({"health": False})
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(provider.calls, 0)
        self.assertEqual(manager.provider_skip_count, 1)


if __name__ == "__main__":
    unittest.main()
