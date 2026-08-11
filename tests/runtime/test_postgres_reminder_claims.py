from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from apps.assistant.src.adapters.postgres_reminder_claims import PostgresReminderClaimRepository
from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.modules.reminder import ReminderRecord, ReminderSource
from apps.assistant.src.modules.reminder_scheduler import ReminderDeliveryClaim


NOW = datetime(2026, 8, 11, 13, tzinfo=timezone.utc)


class FakeCursor:
    def __init__(self, rows=None, rowcount=1):
        self.rows = list(rows or [])
        self.rowcount = rowcount
        self.executed = []
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return False
    def execute(self, sql, params=None): self.executed.append((sql, params))
    def fetchone(self): return self.rows[0] if self.rows else None
    def fetchall(self): return list(self.rows)


class FakeConnection:
    def __init__(self, cursor): self._cursor = cursor
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return False
    def cursor(self): return self._cursor


class Connector:
    def __init__(self, cursors):
        self._cursors = list(cursors)
        self.calls = []
    def __call__(self, dsn, **kwargs):
        self.calls.append((dsn, kwargs))
        return FakeConnection(self._cursors.pop(0))


def claim_row():
    return (
        "22222222-2222-2222-2222-222222222222",
        "user",
        "owner",
        "11111111-1111-1111-1111-111111111111",
        NOW - timedelta(seconds=1),
        "todo_due",
        "creator-node",
        NOW - timedelta(days=1),
        "scheduled",
        None,
        "33333333-3333-3333-3333-333333333333",
        "core-home-01",
        NOW + timedelta(seconds=30),
        2,
        NOW,
    )


def claim():
    row = claim_row()
    return ReminderDeliveryClaim(
        reminder=ReminderRecord(
            reminder_id=row[0],
            scope=MemoryScope.USER,
            scope_id=row[2],
            todo_id=row[3],
            fire_at=row[4],
            source=ReminderSource.TODO_DUE,
            created_by_node_id=row[6],
            created_at=row[7],
        ),
        claim_token=row[10],
        claim_owner=row[11],
        claim_until=row[12],
        attempt_count=row[13],
        claimed_at=row[14],
    )


class PostgresReminderClaimRepositoryTests(unittest.TestCase):
    def test_claim_uses_skip_locked_and_accepts_expired_lease_recovery(self):
        schema = FakeCursor()
        query = FakeCursor([claim_row()])
        connector = Connector([schema, query])
        repository = PostgresReminderClaimRepository("postgresql://db/hearthghost", connect=connector)
        result = repository.claim_due(
            now=NOW,
            claim_owner="core-home-01",
            claim_until=NOW + timedelta(seconds=30),
        )
        sql, params = query.executed[0]
        self.assertIn("FOR UPDATE SKIP LOCKED", sql)
        self.assertIn("delivery_state = 'pending'", sql)
        self.assertIn("delivery_state = 'claimed' AND claim_until <= %s", sql)
        self.assertIn("record.attempt_count + 1", sql)
        self.assertEqual(params[0:3], (NOW, NOW, NOW))
        self.assertEqual(result.reminder.scope, MemoryScope.USER)
        self.assertEqual(result.attempt_count, 2)

    def test_claim_validation_rechecks_scope_token_owner_fire_at_and_lease(self):
        schema = FakeCursor()
        validate = FakeCursor([(1,)])
        connector = Connector([schema, validate])
        repository = PostgresReminderClaimRepository("postgresql://db/hearthghost", connect=connector)
        self.assertTrue(repository.claim_is_current(claim()))
        sql, params = validate.executed[0]
        self.assertIn("scope = %s", sql)
        self.assertIn("scope_id = %s", sql)
        self.assertIn("claim_token = %s", sql)
        self.assertIn("claim_owner = %s", sql)
        self.assertIn("claim_until > CURRENT_TIMESTAMP", sql)
        self.assertIn("fire_at = %s", sql)
        self.assertEqual(params[0:3], (claim().reminder.reminder_id, "user", "owner"))

    def test_finish_requires_current_exact_claim(self):
        schema = FakeCursor()
        update = FakeCursor(rowcount=1)
        connector = Connector([schema, update])
        repository = PostgresReminderClaimRepository("postgresql://db/hearthghost", connect=connector)
        self.assertTrue(
            repository.mark_delivered(claim(), delivered_at=NOW + timedelta(seconds=1), reason="delivered")
        )
        sql, params = update.executed[0]
        self.assertIn("delivery_state = 'claimed'", sql)
        self.assertIn("claim_token = %s", sql)
        self.assertIn("claim_owner = %s", sql)
        self.assertIn("fire_at = %s", sql)
        self.assertEqual(params[0], "delivered")

    def test_retry_releases_claim_with_next_attempt_and_reason(self):
        schema = FakeCursor()
        update = FakeCursor(rowcount=1)
        connector = Connector([schema, update])
        repository = PostgresReminderClaimRepository("postgresql://db/hearthghost", connect=connector)
        retry_at = NOW + timedelta(minutes=2)
        self.assertTrue(repository.mark_retry(claim(), next_attempt_at=retry_at, reason="node_offline"))
        _, params = update.executed[0]
        self.assertEqual(params[0], "pending")
        self.assertEqual(params[1], retry_at)
        self.assertEqual(params[3], "node_offline")

    def test_zero_row_finish_reports_lost_claim(self):
        connector = Connector([FakeCursor(), FakeCursor(rowcount=0)])
        repository = PostgresReminderClaimRepository("postgresql://db/hearthghost", connect=connector)
        self.assertFalse(repository.mark_exhausted(claim(), reason="too_many_attempts"))

    def test_dsn_is_redacted(self):
        connector = Connector([FakeCursor()])
        repository = PostgresReminderClaimRepository("postgresql://u:secret@db/hearthghost", connect=connector)
        self.assertNotIn("secret", repr(repository))


if __name__ == "__main__":
    unittest.main()
