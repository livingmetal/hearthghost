"""Explicit, synthetic OpenAI connectivity check through Privacy Gateway."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping

from apps.assistant.src.adapters.openai_responses import OpenAIConfigurationError
from apps.assistant.src.modules.orchestrator import HEARTHGHOST_INSTRUCTIONS
from apps.assistant.src.modules.privacy_gateway import (
    DEFAULT_CLOUD_PRIVACY_POLICY,
    DataModality,
    PrivacyGateway,
)
from apps.assistant.src.ports.llm import LLMPort, LLMRequest
from apps.assistant.src.runtime.llm_selection import select_llm_adapter


SMOKE_INPUT = (
    "This is a synthetic HearthGhost provider connectivity check. "
    "Reply with one short sentence confirming text conversation is available."
)
SMOKE_TIMEOUT_SECONDS = 30.0
DEFAULT_SMOKE_MODEL = "gpt-5.6-luna"


def run_smoke(llm: LLMPort) -> tuple[int, dict[str, object]]:
    gateway = PrivacyGateway(
        llm=llm,
        policy=DEFAULT_CLOUD_PRIVACY_POLICY,
    )
    result = gateway.generate(
        DataModality.TEXT,
        LLMRequest(
            request_id="openai-smoke-request",
            conversation_session_id="openai-smoke-session",
            instructions=HEARTHGHOST_INSTRUCTIONS,
            input_text=SMOKE_INPUT,
        ),
        timeout_seconds=SMOKE_TIMEOUT_SECONDS,
    )
    if not result.allowed or result.completion is None:
        return 1, {
            "status": "failed",
            "adapter": "openai",
            "modality": "text",
            "reason": result.reason.value,
        }
    return 0, {
        "status": "ok",
        "adapter": "openai",
        "modality": "text",
        "response_characters": len(result.completion.text),
    }


def main(
    arguments: list[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Run one synthetic text request through the OpenAI adapter",
    )
    parser.add_argument(
        "--adapter",
        required=True,
        choices=("openai",),
        help="provider selection is required; no automatic fallback is available",
    )
    options = parser.parse_args(arguments)
    selected_environment = dict(os.environ if environ is None else environ)
    selected_environment.setdefault("OPENAI_MODEL", DEFAULT_SMOKE_MODEL)
    try:
        llm = select_llm_adapter(options.adapter, environ=selected_environment)
    except OpenAIConfigurationError as error:
        print(
            json.dumps(
                {
                    "status": "configuration_error",
                    "adapter": "openai",
                    "reason": str(error),
                },
                sort_keys=True,
            )
        )
        return 2
    exit_code, report = run_smoke(llm)
    print(json.dumps(report, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
