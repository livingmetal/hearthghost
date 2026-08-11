from __future__ import annotations

import unittest
from datetime import datetime, timezone

from apps.assistant.src.adapters.in_memory_memory import InMemoryMemoryRepository
from apps.assistant.src.modules.memory import (
    MemoryCandidate,
    MemoryKind,
    MemoryManager,
    MemoryScope,
    MemorySource,
)


class Clock:
    def __init__(self) -> None:
        self.current = datetime(2026, 8, 11, tzinfo=timezone.utc)

    def now(self):
        return self.current


class BadScopeRepository(InMemoryMemoryRepository):
    def list_scope(self, scope, scope_id, *, limit):
        records = super().list_scope(scope, scope_id, limit=limit)
        if not records:
            return records
        record = records[0]
        return (record.__class__(
            memory_id=record.memory_id,
            scope=MemoryScope.HOUSEHOLD,
            scope_id="other-household",
            kind=record.kind,
            text=record.text,
            source=record.source,
            source_conversation_session_id=record.source_conversation_session_id,
            created_at=record.created_at,
        ),)


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.repository = InMemoryMemoryRepository()
        self.memory = MemoryManager(repository=self.repository, clock=self.clock)

    def candidate(self, **overrides):
        values = {
            "scope": MemoryScope.USER,
            "scope_id": "owner",
            "kind": MemoryKind.SEMANTIC,
            "text": "My preferred coffee is a flat white.",
            "source": MemorySource.ADDRESSED_TEXT,
            "source_conversation_session_id": "conversation-1",
            "explicit_user_request": True,
        }
        values.update(overrides)
        return MemoryCandidate(**values)

    def test_explicit_addressed_text_can_be_remembered(self):
        record = self.memory.remember(self.candidate())

        self.assertEqual(record.scope, MemoryScope.USER)
        self.assertEqual(record.scope_id, "owner")
        self.assertEqual(record.text, "My preferred coffee is a flat white.")
        self.assertEqual(self.memory.list_scope(MemoryScope.USER, "owner"), (record,))

    def test_passive_observation_cannot_be_remembered(self):
        with self.assertRaisesRegex(ValueError, "explicit user request"):
            self.memory.remember(self.candidate(explicit_user_request=False))

    def test_only_addressed_text_source_is_accepted(self):
        candidate = self.candidate(source="camera_snapshot", text="camera frame")

        with self.assertRaisesRegex(ValueError, "addressed text"):
            self.memory.remember(candidate)

    def test_scope_isolation_blocks_cross_scope_read_and_delete(self):
        record = self.memory.remember(self.candidate())

        self.assertEqual(self.memory.list_scope(MemoryScope.HOUSEHOLD, "home"), ())
        self.assertFalse(
            self.memory.forget(
                record.memory_id,
                scope=MemoryScope.HOUSEHOLD,
                scope_id="home",
            )
        )
        self.assertTrue(
            self.memory.forget(record.memory_id, scope=MemoryScope.USER, scope_id="owner")
        )

    def test_repository_scope_confusion_fails_closed(self):
        repository = BadScopeRepository()
        memory = MemoryManager(repository=repository, clock=self.clock)
        memory.remember(self.candidate())

        with self.assertRaisesRegex(RuntimeError, "invalid scope data"):
            memory.list_scope(MemoryScope.USER, "owner")

    def test_text_and_retrieval_bounds_are_enforced(self):
        with self.assertRaises(ValueError):
            self.memory.remember(self.candidate(text="x" * 2001))
        with self.assertRaises(ValueError):
            self.memory.list_scope(MemoryScope.USER, "owner", limit=51)
        with self.assertRaises(ValueError):
            self.memory.list_scope(MemoryScope.USER, "owner", limit=True)


if __name__ == "__main__":
    unittest.main()
