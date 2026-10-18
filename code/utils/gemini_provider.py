"""Google Gemini adapter using the installed google-genai SDK."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from .provider_manager import PermanentProviderError, TransientProviderError


class GeminiProvider:
    model = "gemini-2.5-flash"

    def __init__(self, api_key: str, key_index: int) -> None:
        self.api_key = api_key
        self.key_index = key_index
        self.name = f"gemini_{key_index}"
        self._client = None

    def _get_client(self):
        if not self.api_key:
            return None
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def health_check(self) -> bool:
        # Configuration health is deliberately local; requests are made only by execute().
        return self._get_client() is not None

    def execute(self, request: Mapping[str, Any], media_bytes: bytes = b"") -> Any:
        client = self._get_client()
        if client is None:
            raise PermanentProviderError("GOOGLE_API_KEY or GEMINI_API_KEY is not configured")

        operation = request.get("operation")
        if operation == "startup_check":
            schema = None
            contents = "ping"
        elif operation == "perception":
            schema = {
                "type": "OBJECT",
                "properties": {
                    "text": {"type": "STRING", "nullable": True},
                    "confidence": {"type": "NUMBER", "nullable": True},
                },
                "required": ["text", "confidence"],
            }
            prompt = request.get("prompt", "Extract the visible or spoken message content.")
            mime_type = request.get("mime_type", "application/octet-stream")
            from google.genai import types

            contents = [str(prompt), types.Part.from_bytes(data=media_bytes, mime_type=mime_type)]
        elif operation == "content_judgment":
            schema = {
                "type": "OBJECT",
                "properties": {
                    "label": {
                        "type": "STRING",
                        "enum": ["genuine_urgency", "generic_forward", "ambiguous"],
                    },
                    "confidence": {"type": "NUMBER"},
                },
                "required": ["label", "confidence"],
            }
            contents = str(request.get("prompt", "Classify the message semantics."))
        else:
            raise PermanentProviderError(f"unsupported Gemini operation: {operation!r}")

        try:
            from google.genai import types

            config = types.GenerateContentConfig(temperature=0, maxOutputTokens=1)
            if schema is not None:
                config = types.GenerateContentConfig(
                    temperature=0,
                    maxOutputTokens=256,
                    responseMimeType="application/json",
                    responseSchema=schema,
                )
            response = client.models.generate_content(model=self.model, contents=contents, config=config)
        except Exception as exc:  # SDK error types vary by transport/version.
            status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
            message = str(exc).lower()
            if status == 429 or "quota" in message or "resource exhausted" in message:
                raise PermanentProviderError(str(exc), "quota_exhausted") from exc
            if status in {408, 409} or any(token in message for token in ("timeout", "timed out", "connection", "dns", "socket", "temporarily unavailable", "winerror 10013")):
                raise TransientProviderError(str(exc), "transient_network_failure") from exc
            if status in {401, 403} or any(token in message for token in ("api key", "unauthorized", "authentication", "permission denied")):
                raise PermanentProviderError(str(exc), "invalid_key" if "api key" in message else "authentication") from exc
            if status == 404 or "model" in message and "not found" in message:
                raise PermanentProviderError(str(exc), "model_unavailable") from exc
            if isinstance(exc, (ImportError, AttributeError, TypeError)):
                raise PermanentProviderError(str(exc), "sdk_incompatibility") from exc
            raise PermanentProviderError(str(exc), "configuration_error") from exc

        if operation == "startup_check":
            return {"status": "success", "text": getattr(response, "text", "")}

        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            if hasattr(parsed, "model_dump"):
                parsed = parsed.model_dump()
            elif not isinstance(parsed, dict):
                parsed = dict(parsed)
            return parsed
        text = getattr(response, "text", None)
        if not text:
            raise PermanentProviderError("Gemini returned an empty response")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise PermanentProviderError("Gemini returned non-JSON structured output") from exc


def gemini_provider_pool_from_environment() -> dict[str, GeminiProvider]:
    if not os.getenv("GEMINI_API_KEYS"):
        try:
            from dotenv import load_dotenv

            module_path = Path(__file__).resolve()
            for env_path in (module_path.parents[2] / ".env", module_path.parents[1] / ".env"):
                if env_path.is_file():
                    load_dotenv(env_path, override=False)
        except ImportError:
            pass
    raw = os.getenv("GEMINI_API_KEYS")
    if raw is None:
        raise ValueError("GEMINI_API_KEYS is not configured")
    keys = [value.strip() for value in raw.split(",") if value.strip()]
    if not keys:
        raise ValueError("GEMINI_API_KEYS contains no usable keys")
    return {f"gemini_{index}": GeminiProvider(key, index) for index, key in enumerate(keys)}
