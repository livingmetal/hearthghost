"""Server-only OpenAI Responses API adapter using Python's standard library.

No request is made during construction. Live use requires explicit adapter
selection plus a server-side API key. Tests inject a fake HTTP opener.
"""

from __future__ import annotations

import json
import os
import socket
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import BinaryIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from apps.assistant.src.ports.llm import (
    LLMCompletion,
    LLMProviderError,
    LLMRequest,
    LLMTimeoutError,
    LLMUnavailableError,
)


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-5.6"
DEFAULT_MAX_OUTPUT_TOKENS = 1_024
MAX_OUTPUT_TOKENS = 1_024
MAX_RESPONSE_BYTES = 1_048_576
MAX_API_KEY_BYTES = 16_384


class OpenAIConfigurationError(LLMUnavailableError):
    pass


OpenCall = Callable[[Request, float], BinaryIO]


def _open(request: Request, timeout_seconds: float) -> BinaryIO:
    return urlopen(request, timeout=timeout_seconds)


class OpenAIResponsesAdapter:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        open_call: OpenCall = _open,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise OpenAIConfigurationError(
                "OpenAI adapter selected but OPENAI_API_KEY is not configured"
            )
        if not isinstance(model, str) or not model.strip():
            raise OpenAIConfigurationError("OpenAI adapter requires a model")
        if (
            not isinstance(max_output_tokens, int)
            or isinstance(max_output_tokens, bool)
            or max_output_tokens <= 0
            or max_output_tokens > MAX_OUTPUT_TOKENS
        ):
            raise OpenAIConfigurationError(
                f"OpenAI adapter requires an output-token limit between 1 and {MAX_OUTPUT_TOKENS}"
            )
        self._api_key = api_key.strip()
        self._model = model.strip()
        self._max_output_tokens = max_output_tokens
        self._open_call = open_call

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        open_call: OpenCall = _open,
    ) -> OpenAIResponsesAdapter:
        selected = os.environ if environ is None else environ
        api_key = selected.get("OPENAI_API_KEY", "").strip()
        api_key_file = selected.get("OPENAI_API_KEY_FILE", "").strip()
        if api_key and api_key_file:
            raise OpenAIConfigurationError(
                "Configure exactly one of OPENAI_API_KEY or OPENAI_API_KEY_FILE"
            )
        if api_key_file:
            api_key = _read_api_key_file(api_key_file)
        max_output_tokens = _read_max_output_tokens(
            selected.get("OPENAI_MAX_OUTPUT_TOKENS", "")
        )
        return cls(
            api_key=api_key,
            model=selected.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
            max_output_tokens=max_output_tokens,
            open_call=open_call,
        )

    def __repr__(self) -> str:
        return f"OpenAIResponsesAdapter(model={self._model!r}, api_key=<redacted>)"

    def generate(self, request: LLMRequest, *, timeout_seconds: float) -> LLMCompletion:
        if not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
            raise LLMProviderError("OpenAI request timeout must be positive")
        payload = json.dumps(
            {
                "model": self._model,
                "instructions": request.instructions,
                "input": request.input_text,
                "store": False,
                "max_output_tokens": self._max_output_tokens,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        http_request = Request(
            OPENAI_RESPONSES_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self._open_call(http_request, float(timeout_seconds)) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (TimeoutError, socket.timeout) as error:
            raise LLMTimeoutError("OpenAI request timed out") from error
        except HTTPError as error:
            if error.code == 429 or error.code >= 500:
                raise LLMUnavailableError(
                    f"OpenAI service unavailable (HTTP {error.code})"
                ) from error
            raise LLMProviderError(
                f"OpenAI request failed (HTTP {error.code})"
            ) from error
        except URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise LLMTimeoutError("OpenAI request timed out") from error
            raise LLMUnavailableError("OpenAI service unavailable") from error
        except OSError as error:
            raise LLMUnavailableError("OpenAI service unavailable") from error

        if len(raw) > MAX_RESPONSE_BYTES:
            raise LLMProviderError("OpenAI response exceeded the configured limit")
        try:
            decoded = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise LLMProviderError("OpenAI returned malformed JSON") from error
        if not isinstance(decoded, dict) or decoded.get("status") != "completed":
            raise LLMProviderError("OpenAI response did not complete")
        text = _extract_output_text(decoded)
        if not text:
            raise LLMProviderError("OpenAI response contained no text output")
        return LLMCompletion(text)


def _read_api_key_file(path_value: str) -> str:
    path = Path(path_value)
    try:
        if path.is_symlink() or not path.is_file():
            raise OpenAIConfigurationError(
                "OPENAI_API_KEY_FILE must reference a regular secret file"
            )
        with path.open("rb") as secret_file:
            raw = secret_file.read(MAX_API_KEY_BYTES + 1)
    except OpenAIConfigurationError:
        raise
    except OSError as error:
        raise OpenAIConfigurationError(
            "OpenAI API key secret file could not be read"
        ) from error
    if len(raw) > MAX_API_KEY_BYTES:
        raise OpenAIConfigurationError("OpenAI API key secret file is too large")
    try:
        return raw.decode("utf-8").strip()
    except UnicodeDecodeError as error:
        raise OpenAIConfigurationError(
            "OpenAI API key secret file must be UTF-8 text"
        ) from error


def _read_max_output_tokens(value: str) -> int:
    selected = value.strip()
    if not selected:
        return DEFAULT_MAX_OUTPUT_TOKENS
    try:
        parsed = int(selected, 10)
    except ValueError as error:
        raise OpenAIConfigurationError(
            "OPENAI_MAX_OUTPUT_TOKENS must be an integer between 1 and 1024"
        ) from error
    if not 1 <= parsed <= MAX_OUTPUT_TOKENS:
        raise OpenAIConfigurationError(
            "OPENAI_MAX_OUTPUT_TOKENS must be an integer between 1 and 1024"
        )
    return parsed


def _extract_output_text(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    output = payload.get("output")
    if not isinstance(output, list):
        return ""
    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if (
                isinstance(part, dict)
                and part.get("type") == "output_text"
                and isinstance(part.get("text"), str)
            ):
                value = part["text"].strip()
                if value:
                    parts.append(value)
    return "\n".join(parts)
