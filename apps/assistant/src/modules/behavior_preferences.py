"""Validated principal-scoped behavior preference boundary.

Behavior preferences are data, not authority. This module has no API for Hard
Policy, credentials, Node trust, capability grants, tools, provider secrets, or
sensor permissions. It persists exact user/household scopes and never mutates a
process-global Persona or timeout.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from apps.assistant.src.modules.persona import (
    PersonaProfile,
    require_expression_style,
    require_persona_name,
)
from apps.assistant.src.ports.behavior_preferences import (
    BehaviorPreferenceRepository,
    StoredBehaviorPreferences,
)
from apps.assistant.src.ports.node_gateway import Clock


ALLOWED_PATHS = frozenset(
    {
        "character.name",
        "character.humor",
        "character.verbosity",
        "character.formality",
        "character.initiative",
        "character.expression_style",
        "conversation.followup_timeout_sec",
        "proactive.frequency",
    }
)
DEFAULT_FOLLOWUP_TIMEOUT_SEC = 45
DEFAULT_PROACTIVE_FREQUENCY = "low"


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
    """Load and atomically persist one exact principal-scoped preference set."""

    def __init__(
        self,
        *,
        repository: BehaviorPreferenceRepository,
        clock: Clock,
        default_persona: PersonaProfile | None = None,
        default_followup_timeout_sec: int = DEFAULT_FOLLOWUP_TIMEOUT_SEC,
        default_proactive_frequency: str = DEFAULT_PROACTIVE_FREQUENCY,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._default_persona = default_persona or PersonaProfile()
        self._default_followup_timeout_sec = _require_timeout_seconds(default_followup_timeout_sec)
        self._default_proactive_frequency = _require_proactive_frequency(default_proactive_frequency)

    def default_snapshot(self) -> BehaviorPreferenceSnapshot:
        return BehaviorPreferenceSnapshot(
            persona=self._default_persona,
            followup_timeout_sec=self._default_followup_timeout_sec,
            proactive_frequency=self._default_proactive_frequency,
        )

    def snapshot(self, *, scope: str, scope_id: str) -> BehaviorPreferenceSnapshot:
        scope, scope_id = _validate_scope(scope, scope_id)
        stored = self._repository.get(scope, scope_id)
        if stored is None:
            return self.default_snapshot()
        _validate_stored_record(stored, scope=scope, scope_id=scope_id)
        return BehaviorPreferenceSnapshot(
            persona=stored.persona,
            followup_timeout_sec=stored.followup_timeout_sec,
            proactive_frequency=stored.proactive_frequency,
        )

    def apply(
        self,
        changes: Iterable[BehaviorPreferenceChange],
        *,
        scope: str,
        scope_id: str,
        updated_by_node_id: str,
    ) -> BehaviorPreferenceSnapshot:
        scope, scope_id = _validate_scope(scope, scope_id)
        updated_by_node_id = _require_identifier(updated_by_node_id, "updated_by_node_id")
        proposed = tuple(changes)
        if not proposed or len(proposed) > 16:
            raise ValueError("behavior preference update must contain 1 to 16 changes")

        stored = self._repository.get(scope, scope_id)
        if stored is None:
            current = self.default_snapshot()
            expected_revision = None
            next_revision = 1
        else:
            _validate_stored_record(stored, scope=scope, scope_id=scope_id)
            current = BehaviorPreferenceSnapshot(
                persona=stored.persona,
                followup_timeout_sec=stored.followup_timeout_sec,
                proactive_frequency=stored.proactive_frequency,
            )
            expected_revision = stored.revision
            next_revision = stored.revision + 1

        updated = _apply_changes(current, proposed)
        now = self._clock.now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise RuntimeError("behavior preference clock must return timezone-aware timestamps")
        record = StoredBehaviorPreferences(
            scope=scope,
            scope_id=scope_id,
            persona=updated.persona,
            followup_timeout_sec=updated.followup_timeout_sec,
            proactive_frequency=updated.proactive_frequency,
            revision=next_revision,
            updated_at=now,
            updated_by_node_id=updated_by_node_id,
        )
        persisted = self._repository.put(record, expected_revision=expected_revision)
        _validate_stored_record(persisted, scope=scope, scope_id=scope_id)
        if persisted.revision != next_revision:
            raise RuntimeError("behavior preference repository returned an unexpected revision")
        return BehaviorPreferenceSnapshot(
            persona=persisted.persona,
            followup_timeout_sec=persisted.followup_timeout_sec,
            proactive_frequency=persisted.proactive_frequency,
        )


def _apply_changes(
    current: BehaviorPreferenceSnapshot,
    proposed: tuple[BehaviorPreferenceChange, ...],
) -> BehaviorPreferenceSnapshot:
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
        elif change.path == "character.expression_style":
            persona = replace(persona, expression_style=require_expression_style(change.value))
        elif change.path == "conversation.followup_timeout_sec":
            followup_timeout_sec = _require_timeout_seconds(change.value)
        elif change.path == "proactive.frequency":
            proactive_frequency = _require_proactive_frequency(change.value)

    return BehaviorPreferenceSnapshot(persona, followup_timeout_sec, proactive_frequency)


def _validate_stored_record(
    record: StoredBehaviorPreferences,
    *,
    scope: str,
    scope_id: str,
) -> None:
    if not isinstance(record, StoredBehaviorPreferences):
        raise RuntimeError("behavior preference repository returned an invalid record")
    if record.scope != scope or record.scope_id != scope_id:
        raise RuntimeError("behavior preference repository crossed principal scope")
    if not isinstance(record.persona, PersonaProfile):
        raise RuntimeError("behavior preference repository returned an invalid Persona")
    _require_timeout_seconds(record.followup_timeout_sec)
    _require_proactive_frequency(record.proactive_frequency)
    if not isinstance(record.revision, int) or isinstance(record.revision, bool) or record.revision <= 0:
        raise RuntimeError("behavior preference repository returned an invalid revision")
    if record.updated_at.tzinfo is None or record.updated_at.utcoffset() is None:
        raise RuntimeError("behavior preference repository returned a naive timestamp")
    _require_identifier(record.updated_by_node_id, "updated_by_node_id")


def _validate_scope(scope: object, scope_id: object) -> tuple[str, str]:
    if scope not in {"user", "household"}:
        raise ValueError("behavior preference scope must be user or household")
    return str(scope), _require_identifier(scope_id, "scope_id")


def _require_identifier(value: object, name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 128
        or "\x00" in value
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError(f"{name} is invalid")
    return value


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
