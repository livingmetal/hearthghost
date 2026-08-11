"""Persistence boundary for principal-scoped behavior preferences."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from apps.assistant.src.modules.persona import PersonaProfile


class BehaviorPreferenceConflictError(RuntimeError):
    """Optimistic-write conflict; callers must reload rather than overwrite."""


@dataclass(frozen=True)
class StoredBehaviorPreferences:
    scope: str
    scope_id: str
    persona: PersonaProfile
    followup_timeout_sec: int
    proactive_frequency: str
    revision: int
    updated_at: datetime
    updated_by_node_id: str


class BehaviorPreferenceRepository(Protocol):
    def get(self, scope: str, scope_id: str) -> StoredBehaviorPreferences | None: ...

    def put(
        self,
        record: StoredBehaviorPreferences,
        *,
        expected_revision: int | None,
    ) -> StoredBehaviorPreferences: ...
