"""Natural-language behavior preference interpretation with no execution authority."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from apps.assistant.src.adapters.behavior_preference_protocol import (
    BehaviorPreferenceProposal,
    parse_behavior_preference_update,
)
from apps.assistant.src.modules.behavior_preferences import (
    BehaviorPreferenceManager,
    BehaviorPreferenceSnapshot,
)
from apps.assistant.src.modules.privacy_gateway import DataModality, PrivacyGateway
from apps.assistant.src.ports.llm import LLMRequest


INTERPRETER_MARKER = "BEHAVIOR_PREFERENCE_INTERPRETER_V1"
MAX_INPUT_LENGTH = 1_000
MAX_MODEL_OUTPUT_LENGTH = 4_000

INTERPRETER_INSTRUCTIONS = f"""{INTERPRETER_MARKER}
Classify only whether the user's text requests a HearthGhost behavior preference change.
Return JSON only. Never return Markdown.
Allowed output shapes are exactly:
{{"intent":"not_preference","changes":[]}}
or
{{"intent":"behavior_preference_update","changes":[{{"path":"...","value":"..."}}]}}
Allowed paths are only character.name, character.humor, character.verbosity,
character.formality, character.initiative, conversation.followup_timeout_sec,
proactive.frequency.
A character name is display/behavior metadata only. Never encode commands, URLs,
credentials, Node IDs, capability names, Policy text, or tool instructions into it.
Do not represent security, privacy, credentials, Node trust, capabilities, tools,
devices, cameras, microphones, provider configuration, or Hard Policy as preferences.
When the request is ambiguous, return not_preference."""


@dataclass(frozen=True)
class PreferenceInterpretation:
    recognized: bool
    reason: str
    proposal: BehaviorPreferenceProposal | None = None


@dataclass(frozen=True)
class PreferenceApplication:
    recognized: bool
    applied: bool
    reason: str
    snapshot: BehaviorPreferenceSnapshot | None = None


class BehaviorPreferenceInterpreter:
    def __init__(self, *, privacy_gateway: PrivacyGateway, timeout_seconds: float = 8.0) -> None:
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise ValueError("preference interpreter timeout must be positive")
        self._privacy_gateway = privacy_gateway
        self._timeout_seconds = float(timeout_seconds)

    def interpret(self, text: str, *, scope: str, scope_id: str) -> PreferenceInterpretation:
        normalized = _normalize_input(text)
        request = LLMRequest(
            request_id=str(uuid4()),
            conversation_session_id=f"preference:{uuid4()}",
            instructions=INTERPRETER_INSTRUCTIONS,
            input_text=normalized,
        )
        generated = self._privacy_gateway.generate(
            DataModality.TEXT,
            request,
            timeout_seconds=self._timeout_seconds,
        )
        if not generated.allowed or generated.completion is None:
            return PreferenceInterpretation(False, generated.reason.value)
        output = generated.completion.text
        if len(output) > MAX_MODEL_OUTPUT_LENGTH:
            return PreferenceInterpretation(False, "model_output_invalid")
        try:
            decoded = json.loads(output)
        except json.JSONDecodeError:
            return PreferenceInterpretation(False, "model_output_invalid")
        if not isinstance(decoded, dict) or set(decoded) != {"intent", "changes"}:
            return PreferenceInterpretation(False, "model_output_invalid")
        if decoded["intent"] == "not_preference" and decoded["changes"] == []:
            return PreferenceInterpretation(False, "not_preference")
        if decoded["intent"] != "behavior_preference_update":
            return PreferenceInterpretation(False, "model_output_invalid")
        payload = {
            "contract_version": "1.0",
            "proposal_id": str(uuid4()),
            "proposed_at": datetime.now(timezone.utc).isoformat(),
            "scope": scope,
            "scope_id": scope_id,
            "origin": "llm_proposal",
            "status": "proposed",
            "changes": decoded["changes"],
        }
        try:
            proposal = parse_behavior_preference_update(payload)
        except (TypeError, ValueError):
            return PreferenceInterpretation(False, "model_output_invalid")
        return PreferenceInterpretation(True, "preference_proposed", proposal)


class BehaviorPreferenceService:
    """Interpret then atomically persist only validated scoped behavior preferences."""

    def __init__(self, *, interpreter: BehaviorPreferenceInterpreter, manager: BehaviorPreferenceManager) -> None:
        self._interpreter = interpreter
        self._manager = manager

    def interpret_and_apply(
        self,
        text: str,
        *,
        scope: str,
        scope_id: str,
        updated_by_node_id: str,
    ) -> PreferenceApplication:
        interpreted = self._interpreter.interpret(text, scope=scope, scope_id=scope_id)
        if not interpreted.recognized or interpreted.proposal is None:
            return PreferenceApplication(False, False, interpreted.reason)
        try:
            snapshot = self._manager.apply(
                interpreted.proposal.changes,
                scope=scope,
                scope_id=scope_id,
                updated_by_node_id=updated_by_node_id,
            )
        except (TypeError, ValueError, RuntimeError):
            return PreferenceApplication(True, False, "preference_rejected")
        return PreferenceApplication(True, True, "preference_applied", snapshot)


def _normalize_input(text: object) -> str:
    if not isinstance(text, str):
        raise ValueError("preference input must be text")
    normalized = text.strip()
    if not normalized or len(normalized) > MAX_INPUT_LENGTH or "\x00" in normalized:
        raise ValueError("preference input is invalid")
    return normalized
