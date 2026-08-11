"""In-memory scoped behavior preference repository for tests and deny-small defaults."""

from __future__ import annotations

from apps.assistant.src.ports.behavior_preferences import (
    BehaviorPreferenceConflictError,
    StoredBehaviorPreferences,
)


class InMemoryBehaviorPreferenceRepository:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], StoredBehaviorPreferences] = {}

    def get(self, scope: str, scope_id: str) -> StoredBehaviorPreferences | None:
        return self._records.get((scope, scope_id))

    def put(
        self,
        record: StoredBehaviorPreferences,
        *,
        expected_revision: int | None,
    ) -> StoredBehaviorPreferences:
        key = (record.scope, record.scope_id)
        current = self._records.get(key)
        if expected_revision is None:
            if current is not None:
                raise BehaviorPreferenceConflictError("behavior preference record already exists")
        elif current is None or current.revision != expected_revision:
            raise BehaviorPreferenceConflictError("behavior preference revision changed")
        self._records[key] = record
        return record
