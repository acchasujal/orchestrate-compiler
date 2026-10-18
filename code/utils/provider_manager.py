"""Provider-neutral execution, retry, health, and degraded-response infrastructure."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol


class ProviderError(RuntimeError):
    """Base provider failure."""

    category = "provider_error"


class PermanentProviderError(ProviderError):
    """A provider failure that must not be retried."""

    def __init__(self, message: str, category: str = "permanent_provider_failure") -> None:
        super().__init__(message)
        self.category = category


class TransientProviderError(ProviderError):
    """A provider failure that may be retried."""

    def __init__(self, message: str, category: str = "transient_network_failure") -> None:
        super().__init__(message)
        self.category = category


class Provider(Protocol):
    name: str
    model: str

    def health_check(self) -> bool: ...

    def execute(self, request: Mapping[str, Any], media_bytes: bytes = b"") -> Any: ...


@dataclass(frozen=True)
class RequestKey:
    provider: str
    model: str
    prompt_version: str
    request_payload: Mapping[str, Any]
    media_bytes: bytes = b""

    def digest(self) -> str:
        payload = json.dumps(self.request_payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        material = b"|".join((self.provider.encode(), self.model.encode(), self.prompt_version.encode(), payload, self.media_bytes))
        return hashlib.sha256(material).hexdigest()


class CacheManager:
    """Persistent JSON cache for successful responses and permanent failures."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _path(self, digest: str, namespace: str = "judgment", permanent: bool = False) -> Path:
        directory = self.root / ("failures" if permanent else namespace)
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{digest}.json"

    def get(self, digest: str, namespace: str = "judgment") -> dict[str, Any] | None:
        for path in (self._path(digest, namespace), self._path(digest, permanent=True)):
            if path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))
        return None

    def put_success(self, key: RequestKey, response: Any, namespace: str = "judgment") -> None:
        self._write(self._path(key.digest(), namespace), {"request_hash": key.digest(), "provider": key.provider, "model": key.model, "timestamp": _now(), "status": "success", "response": response})

    def put_permanent_failure(self, key: RequestKey, reason: str, category: str = "permanent_provider_failure") -> None:
        self._write(self._path(key.digest(), permanent=True), {"request_hash": key.digest(), "provider": key.provider, "model": key.model, "timestamp": _now(), "status": "permanent_failure", "failure_reason": reason, "failure_category": category})

    @staticmethod
    def _write(path: Path, value: dict[str, Any]) -> None:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        temporary.replace(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ProviderConfig:
    mode: str = "stub"
    provider_name: str = "stub"
    model: str = "stub-v1"
    prompt_version: str = "v1"
    max_retries: int = 2
    cache_root: Path = Path("cache")

    @classmethod
    def from_environment(cls) -> "ProviderConfig":
        return cls(
            mode=os.getenv("ORCHESTRATE_PROVIDER_MODE", "stub"),
            provider_name=os.getenv("ORCHESTRATE_PROVIDER", "stub"),
            model=os.getenv("ORCHESTRATE_MODEL", "stub-v1"),
            prompt_version=os.getenv("ORCHESTRATE_PROMPT_VERSION", "v1"),
            max_retries=int(os.getenv("ORCHESTRATE_MAX_RETRIES", "2")),
            cache_root=Path(os.getenv("ORCHESTRATE_CACHE_DIR", "cache")),
        )


@dataclass(frozen=True)
class StartupHealthResult:
    configured_key_count: int
    tested_key_count: int
    active_key_index: int | None
    healthy: bool
    failures: tuple[tuple[int, str], ...]


@dataclass
class ProviderState:
    key_index: int
    health: bool = False
    request_count: int = 0
    permanent_failure: bool = False
    last_failure_reason: str | None = None
    last_success_timestamp: str | None = None


class ProviderManager:
    """Single provider execution boundary used by future provider-backed modules."""

    def __init__(self, config: ProviderConfig, providers: Mapping[str, Provider]) -> None:
        if config.max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if config.mode not in {"real", "stub", "fallback"}:
            raise ValueError(f"unsupported provider mode: {config.mode!r}")
        self.config = config
        self.providers = dict(providers)
        self.cache = CacheManager(config.cache_root)
        self.provider_call_count = 0
        self.cache_hit_count = 0
        self.cache_miss_count = 0
        self.provider_skip_count = 0
        self.active_provider_index = 0
        self.provider_names = list(self.providers)
        if config.provider_name in self.provider_names:
            self.active_provider_index = self.provider_names.index(config.provider_name)
        self.provider_states = {index: ProviderState(index) for index in range(len(self.provider_names))}
        self.provider_call_counts: dict[int, int] = {index: 0 for index in range(len(self.provider_names))}
        self.provider_call_log: list[dict[str, Any]] = []
        self.startup_health_result: StartupHealthResult | None = None
        self.available = self.health_check()

    def health_check(self) -> bool:
        provider = self._active_provider()
        return bool(provider and provider.health_check())

    def _active_provider(self) -> Provider | None:
        names = self.provider_names
        if not names:
            return None
        self.active_provider_index = min(self.active_provider_index, len(names) - 1)
        return self.providers.get(names[self.active_provider_index])

    def rotate_provider(self) -> bool:
        if self.active_provider_index + 1 >= len(self.providers):
            return False
        self.active_provider_index += 1
        self.available = self.health_check()
        return self.available

    def startup_health_check(self) -> StartupHealthResult:
        """Make one tiny request per key until one succeeds; never retries a key."""
        key_count = len(self.providers)
        failures: list[tuple[int, str]] = []
        for index in range(key_count):
            self.active_provider_index = index
            self.available = self.health_check()
            if not self.available:
                failures.append((index, "configuration_error"))
                continue
            result = self.execute(
                {"operation": "startup_check", "prompt": "ping"},
                namespace="startup",
                max_retries_override=0,
                rotate_on_permanent=False,
            )
            if isinstance(result, Mapping) and result.get("status") == "degraded":
                failures.append((index, str(result.get("failure_category", "provider_error"))))
                self.provider_states[index].health = False
                continue
            self.provider_states[index].health = True
            self.startup_health_result = StartupHealthResult(key_count, index + 1, index, True, tuple(failures))
            return self.startup_health_result
        self.available = False
        self.startup_health_result = StartupHealthResult(key_count, key_count, None, False, tuple(failures))
        return self.startup_health_result

    def execute(
        self,
        request: Mapping[str, Any],
        media_bytes: bytes = b"",
        namespace: str = "judgment",
        max_retries_override: int | None = None,
        rotate_on_permanent: bool = True,
    ) -> Any:
        if self.config.mode == "fallback":
            self.provider_skip_count += 1
            return {"status": "degraded", "reason": "provider mode is fallback", "failure_category": "configuration_error"}
        provider = self._active_provider()
        if provider is None or not self.available:
            self.provider_skip_count += 1
            return {"status": "degraded", "reason": "provider unavailable", "failure_category": "configuration_error"}
        key = RequestKey(provider.name, provider.model, self.config.prompt_version, request, media_bytes)
        cached = self.cache.get(key.digest(), namespace)
        if cached is not None:
            self.cache_hit_count += 1
            if cached["status"] == "success":
                return cached["response"]
            return {
                "status": "degraded",
                "reason": cached.get("failure_reason", "permanent provider failure"),
                "failure_category": cached.get("failure_category", "permanent_provider_failure"),
            }
        self.cache_miss_count += 1
        attempts = 0
        max_retries = self.config.max_retries if max_retries_override is None else max_retries_override
        while True:
            try:
                self.provider_call_count += 1
                active_index = self.active_provider_index
                self.provider_call_counts[active_index] += 1
                self.provider_states[active_index].request_count += 1
                self.provider_call_log.append({
                    "key_index": active_index,
                    "request_hash": key.digest(),
                    "namespace": namespace,
                    "operation": str(request.get("operation", "unknown")),
                })
                response = provider.execute(request, media_bytes) if media_bytes else provider.execute(request)
                self.cache.put_success(key, response, namespace)
                self.provider_states[active_index].health = True
                self.provider_states[active_index].last_success_timestamp = _now()
                return response
            except PermanentProviderError as exc:
                self.cache.put_permanent_failure(key, str(exc), exc.category)
                state = self.provider_states[self.active_provider_index]
                state.health = False
                state.permanent_failure = True
                state.last_failure_reason = str(exc)
                if rotate_on_permanent and self.rotate_provider():
                    provider = self._active_provider()
                    if provider is None:
                        return {"status": "degraded", "reason": str(exc), "failure_category": exc.category}
                    key = RequestKey(provider.name, provider.model, self.config.prompt_version, request, media_bytes)
                    cached = self.cache.get(key.digest(), namespace)
                    if cached is not None:
                        self.cache_hit_count += 1
                        if cached["status"] == "success":
                            return cached["response"]
                        return {"status": "degraded", "reason": cached.get("failure_reason", "permanent provider failure"), "failure_category": cached.get("failure_category", "permanent_provider_failure")}
                    self.cache_miss_count += 1
                    attempts = 0
                    continue
                self.available = False
                return {"status": "degraded", "reason": str(exc), "failure_category": exc.category}
            except TransientProviderError as exc:
                state = self.provider_states[self.active_provider_index]
                state.last_failure_reason = str(exc)
                if attempts >= max_retries:
                    return {"status": "degraded", "reason": str(exc), "failure_category": exc.category}
                attempts += 1
                time.sleep(0)
            except Exception as exc:
                state = self.provider_states[self.active_provider_index]
                state.health = False
                state.last_failure_reason = str(exc)
                self.cache.put_permanent_failure(key, str(exc), "permanent_provider_failure")
                return {"status": "degraded", "reason": str(exc), "failure_category": "permanent_provider_failure"}

    def skip(self) -> None:
        """Record a deliberate deterministic provider skip."""
        self.provider_skip_count += 1


class StubProvider:
    name = "stub"
    model = "stub-v1"

    def health_check(self) -> bool:
        return True

    def execute(self, request: Mapping[str, Any], media_bytes: bytes = b"") -> Any:
        return {"status": "stub", "request": dict(request)}
