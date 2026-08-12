from __future__ import annotations

import unittest
from datetime import datetime, timezone

from apps.assistant.src.adapters.postgres_behavior_preferences import PostgresBehaviorPreferenceRepository
from apps.assistant.src.modules.persona import PersonaProfile
from apps.assistant.src.ports.behavior_preferences import (
    BehaviorPreferenceConflictError,
    StoredBehaviorPreferences,
)


class FakeCursor:
    def __init__(self, rows=None, rowcount=1):
        self.rows = list(rows or [])
        self.rowcount = rowcount
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self._cursor


class Connector:
    def __init__(self, cursors):
        self._cursors = list(cursors)
        self.calls = []

    def __call__(self, dsn, **kwargs):
        self.calls.append((dsn, kwargs))
        return FakeConnection(self._cursors.pop(0))


class PostgresBehaviorPreferenceRepositoryTests(unittest.TestCase):
    def record(self, *, revision=1):
        return StoredBehaviorPreferences(
            scope="user",
            scope_id="owner",
            persona=PersonaProfile(
                name="Luna",
                humor="high",
                verbosity="concise",
                formality="neutral",
                initiative="moderate",
                expression_style="yandere",
            ),
            followup_timeout_sec=30,
            proactive_frequency="moderate",
            revision=revision,
            updated_at=datetime(2026, 8, 11, 13, tzinfo=timezone.utc),
            updated_by_node_id="android-personal-01",
        )

    def test_dsn_is_redacted_and_schema_connect_timeout_is_bounded(self):
        connector = Connector([FakeCursor()])
        repository = PostgresBehaviorPreferenceRepository(
            "postgresql://u:secret@db/hearthghost",
            connect=connector,
        )
        self.assertNotIn("secret", repr(repository))
        self.assertEqual(connector.calls[0][1]["connect_timeout"], 5)

    def test_create_uses_parameter_binding_and_exact_scope_key(self):
        schema = FakeCursor()
        write = FakeCursor(rowcount=1)
        connector = Connector([schema, write])
        repository = PostgresBehaviorPreferenceRepository("postgresql://db/hearthghost", connect=connector)
        record = self.record()
        repository.put(record, expected_revision=None)
        sql, params = write.executed[0]
        self.assertIn("INSERT INTO behavior_preference_records", sql)
        self.assertIn("ON CONFLICT (scope, scope_id) DO NOTHING", sql)
        self.assertNotIn(record.persona.name, sql)
        self.assertEqual(params[0:2], ("user", "owner"))
        self.assertEqual(params[2], "Luna")
        self.assertEqual(params[7], "yandere")
        self.assertEqual(params[10], 1)

    def test_update_requires_scope_scope_id_and_expected_revision(self):
        schema = FakeCursor()
        write = FakeCursor(rowcount=1)
        connector = Connector([schema, write])
        repository = PostgresBehaviorPreferenceRepository("postgresql://db/hearthghost", connect=connector)
        repository.put(self.record(revision=2), expected_revision=1)
        sql, params = write.executed[0]
        self.assertIn("WHERE scope = %s AND scope_id = %s AND revision = %s", sql)
        self.assertEqual(params[-3:], ("user", "owner", 1))

    def test_zero_row_write_is_optimistic_conflict(self):
        connector = Connector([FakeCursor(), FakeCursor(rowcount=0)])
        repository = PostgresBehaviorPreferenceRepository("postgresql://db/hearthghost", connect=connector)
        with self.assertRaises(BehaviorPreferenceConflictError):
            repository.put(self.record(revision=2), expected_revision=1)

    def test_get_binds_exact_scope_and_decodes_typed_persona(self):
        row = (
            "user",
            "owner",
            "Luna",
            "high",
            "concise",
            "neutral",
            "moderate",
            30,
            "moderate",
            7,
            datetime(2026, 8, 11, 13, tzinfo=timezone.utc),
            "android-personal-01",
        )
        connector = Connector([FakeCursor(), FakeCursor([row])])
        repository = PostgresBehaviorPreferenceRepository("postgresql://db/hearthghost", connect=connector)
        record = repository.get("user", "owner")
        query = connector._cursors
        self.assertEqual(record.persona.name, "Luna")
        self.assertEqual(record.persona.expression_style, "yandere")
        self.assertEqual(record.revision, 7)
        self.assertEqual(record.followup_timeout_sec, 30)

    def test_get_query_never_omits_scope(self):
        schema = FakeCursor()
        query = FakeCursor()
        connector = Connector([schema, query])
        repository = PostgresBehaviorPreferenceRepository("postgresql://db/hearthghost", connect=connector)
        self.assertIsNone(repository.get("household", "home"))
        sql, params = query.executed[0]
        self.assertIn("WHERE scope = %s AND scope_id = %s", sql)
        self.assertEqual(params, ("household", "home"))

    def test_naive_timestamp_or_invalid_persona_fails_closed_on_decode(self):
        rows = [
            (
                "user", "owner", "Luna", "high", "concise", "neutral", "moderate", "balanced",
                30, "moderate", 1, datetime(2026, 8, 11, 13), "android-personal-01",
            ),
            (
                "user", "owner", "Luna", "invalid", "concise", "neutral", "moderate", "balanced",
                30, "moderate", 1, datetime(2026, 8, 11, 13, tzinfo=timezone.utc), "android-personal-01",
            ),
        ,
            (
                "user", "owner", "Luna", "high", "concise", "neutral", "moderate", "raw-morph",
                30, "moderate", 1, datetime(2026, 8, 11, 13, tzinfo=timezone.utc), "android-personal-01",
            ),
        ]
        for row in rows:
            connector = Connector([FakeCursor(), FakeCursor([row])])
            repository = PostgresBehaviorPreferenceRepository("postgresql://db/hearthghost", connect=connector)
            with self.subTest(row=row), self.assertRaisesRegex(RuntimeError, "invalid record"):
                repository.get("user", "owner")


if __name__ == "__main__":
    unittest.main()
