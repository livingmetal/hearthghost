"""Validated behavior-preference application boundary.

This module applies only paths representable by the public behavior preference
contract. It deliberately has no API for Hard Policy, credentials, Node trust,
tool grants, or provider secrets.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Iterable

from apps.assistant.src.modules.conversation import ConversationManager
from apps.assistant.src.modules.orchestrator import ConversationOrchestrator
from apps.assistant.src.modules.persona import PersonaProfile, require_persona_name


ALLOWED_PATHS = frozenset(
    {
        "character.name",
        "character.humor",
        "character.verbosity",
        "character.formality",
        "character.initiative",
        "conversation.followup_timeout_sec",
        "proactive.frequency",
    }
)


@dataclass(frozen=True)
class BehaviorPreferenceChange:
    path: str
    value: object


@dataclass(frozen=True)
class BehaviorPreferenceSnapshot:
    persona: PersonaProfile
    followup_timeout_sec: int
    proactive_frequency: str


class BehaviorPreferenceManager:
    """Validate an entire update before mutating any runtime preference."""

    def __init__(
        self,
        *,
        conversation: ConversationManager,
        orchestrator: ConversationOrchestrator,
        proactive_frequency: str = "low",
    ) -> None:
        _require_proactive_frequency(proactive_frequency)
        self._conversation = conversation
        self._orchestrator = orchestrator
        self._proactive_frequency = proactive_frequency

    def snapshot(self) -> BehaviorPreferenceSnapshot:
        return BehaviorPreferenceSnapshot(
            persona=self._orchestrator.persona,
            followup_timeout_sec=int(self._conversation.follow_up_timeout.total_seconds()),
            proactive_frequency=self._proactive_frequency,
        )

    def apply(
        self,
        changes: Iterable[BehaviorPreferenceChange],
    ) -> BehaviorPreferenceSnapshot:
        proposed = tuple(changes)
        if not proposed or len(proposed) > 16:
            raise ValueError("behavior preference update must contain 1 to 16 changes")

        current = self.snapshot()
        persona = current.persona
        followup_timeout_sec = current.followup_timeout_sec
        proactive_frequency = current.proactive_frequency
        seen: set[str] = set()

        for change in proposed:
            if not isinstance(change, BehaviorPreferenceChange):
                raise TypeError("changes must contain BehaviorPreferenceChange values")
            if change.path not in ALLOWED_PATHS:
                raise ValueError("behavior preference path is not allowed")
            if change.path in seen:
                raise ValueError("behavior preference path may appear only once per update")
            seen.add(change.path)

            if change.path == "character.name":
                persona = replace(persona, name=require_persona_name(change.value))
            elif change.path == "character.humor":
                persona = replace(persona, humor=_require_string(change.value))
            elif change.path == "character.verbosity":
                persona = replace(persona, verbosity=_require_string(change.value))
            elif change.path == "character.formality":
                persona = replace(persona, formality=_require_string(change.value))
            elif change.path == "character.initiative":
                persona = replace(persona, initiative=_require_string(change.value))
            elif change.path == "conversation.followup_timeout_sec":
                followup_timeout_sec = _require_timeout_seconds(change.value)
            elif change.path == "proactive.frequency":
                proactive_frequency = _require_proactive_frequency(change.value)

        # Validation above constructs a fully valid PersonaProfile and timeout
        # before any live component is changed. Mutations below cannot broaden
        # authorization because these targets hold behavior only.
        self._orchestrator.set_persona(persona)
        self._conversation.set_follow_up_timeout(timedelta(seconds=followup_timeout_sec))
        self._proactive_frequency = proactive_frequency
        return self.snapshot()


def _require_string(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("behavior preference value must be a string")
    return value


def _require_timeout_seconds(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 5 <= value <= 120:
        raise ValueError("follow-up timeout must be an integer from 5 to 120 seconds")
    return value


def _require_proactive_frequency(value: object) -> str:
    if not isinstance(value, str) or value not in {"off", "low", "moderate"}:
        raise ValueError("proactive frequency must be off, low, or moderate")
    return value
