"""Explicit server-side adapter selection; no implicit provider fallback."""

from __future__ import annotations

from collections.abc import Mapping

from apps.assistant.src.adapters.fake_llm import FakeLLMAdapter
from apps.assistant.src.adapters.openai_responses import OpenAIResponsesAdapter
from apps.assistant.src.ports.llm import LLMPort


def select_llm_adapter(
    name: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> LLMPort:
    if name == "fake":
        return FakeLLMAdapter()
    if name == "openai":
        return OpenAIResponsesAdapter.from_environment(environ)
    raise ValueError("LLM adapter must be explicitly selected as 'fake' or 'openai'")
