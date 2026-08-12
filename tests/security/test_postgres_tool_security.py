from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch
import unittest
from uuid import uuid4

from apps.assistant.src.adapters import postgres_tool_security
from apps.assistant.src.adapters.postgres_schema import MIGRATIONS
from apps.assistant.src.adapters.postgres_tool_security import PostgresDecisionReplayProtector
from apps.assistant.src.modules.policy import PolicyEvaluationContext, ToolPolicyEngine
from apps.assistant.src.modules.tool_execution import GuardedToolExecutor
from apps.assistant.src.modules.tools import (
    ActorRole,
    AuditLevel,
    ConfirmationPolicy,
    ToolDefinition,
    ToolEffect,
    ToolProposal,
    ToolRegistry,
    ToolRequiredContext,
    ToolRiskLevel,
)
from apps.assistant.src.ports.llm import ProposedAction
from apps.assistant.src.ports.tools import ToolAdapterResult


NOW = datetime(2026, 8, 13, 3, 0, tzinfo=timezone.utc)


class SharedReplayDatabase:
    def __init__(self) -> None:
        self.consumed: set[str] = set()
        self.connect_calls = 0

    def connect(self, dsn, connect_timeout=5):
        self.connect_calls += 1
        return FakeConnection(self)


class FakeConnection:
    def __init__(self, database: SharedReplayDatabase) -> None:
        self.database = database

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return FakeCursor(self.database)


class FakeCursor:
    def __init__(self, database: SharedReplayDatabase) -> None:
        self.database = database
        self.returned = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, parameters=()):
        normalized = " ".join(str(sql).split())
        if not normalized.startswith("INSERT INTO tool_policy_decision_consumptions"):
            raise AssertionError(f"unexpected replay SQL: {normalized}")
        decision_id = str(parameters[0])
        if decision_id in self.database.consumed:
            self.returned = None
        else:
            self.database.consumed.add(decision_id)
            self.returned = (decision_id,)

    def fetchone(self):
        return self.returned


class FailingReplayProtector:
    def consume(self, decision_id: str) -> bool:
        raise RuntimeError("database unavailable")


class RecordingAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, definition, proposal):
        self.calls += 1
        return ToolAdapterResult(True, "read_ok", {"state": "on"})


def tool_stack():
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="home.entity.read",
            description="Read one approved entity.",
            effect=ToolEffect.EXTERNAL_READ,
            risk_level=ToolRiskLevel.LOW,
            required_context=ToolRequiredContext.EXPLICIT_USER_REQUEST,
            required_roles=frozenset({ActorRole.HOUSEHOLD_MEMBER}),
            confirmation_policy=ConfirmationPolicy.NONE,
            audit_level=AuditLevel.METADATA,
            arguments_schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["device_id"],
                "properties": {"device_id": {"type": "string"}},
            },
            allowed_capabilities=frozenset({"home.entity.read"}),
            allowed_devices=frozenset({"homeassistant.light.room"}),
        )
    )
    policy = ToolPolicyEngine(registry, clock=lambda: NOW)
    proposal = ToolProposal.from_llm_action(
        ProposedAction("home.entity.read", {"device_id": "homeassistant.light.room"}),
        request_id="req-1",
        session_id="session-1",
        node_id="phone-1",
        actor_id="owner",
        explicit_user_request=True,
        now=NOW,
    )
    context = PolicyEvaluationContext(
        request_id="req-1",
        actor_id="owner",
        roles=frozenset({ActorRole.HOUSEHOLD_MEMBER}),
        explicit_user_request=True,
        active_session=True,
        session_id="session-1",
        node_id="phone-1",
        granted_capabilities=frozenset({"home.entity.read"}),
        trusted_device_ids=frozenset({"homeassistant.light.room"}),
    )
    return registry, policy, proposal, policy.evaluate(proposal, context)


class PostgresToolSecurityTests(unittest.TestCase):
    def test_migration_8_creates_durable_replay_ledger(self):
        migration = MIGRATIONS[-1]
        self.assertEqual(migration.version, 8)
        self.assertEqual(migration.name, "tool_policy_decision_replay_v1")
        self.assertIn("CREATE TABLE IF NOT EXISTS tool_policy_decision_consumptions", migration.sql)
        self.assertIn("decision_id UUID PRIMARY KEY", migration.sql)

    def test_postgres_replay_protection_survives_new_protector_instance(self):
        database = SharedReplayDatabase()
        with patch.object(postgres_tool_security, "ensure_postgres_schema") as ensure_schema:
            first = PostgresDecisionReplayProtector("postgresql://example/hearthghost", connect=database.connect)
            second = PostgresDecisionReplayProtector("postgresql://example/hearthghost", connect=database.connect)
        self.assertEqual(ensure_schema.call_count, 2)
        decision_id = str(uuid4())
        self.assertTrue(first.consume(decision_id))
        self.assertFalse(second.consume(decision_id))
        self.assertEqual(database.consumed, {decision_id})

    def test_postgres_replay_protector_redacts_dsn_and_rejects_non_uuid(self):
        database = SharedReplayDatabase()
        with patch.object(postgres_tool_security, "ensure_postgres_schema"):
            protector = PostgresDecisionReplayProtector(
                "postgresql://secret-user:secret-password@example/hearthghost",
                connect=database.connect,
            )
        self.assertEqual(repr(protector), "PostgresDecisionReplayProtector(dsn=<redacted>)")
        with self.assertRaisesRegex(ValueError, "UUID"):
            protector.consume("not-a-decision-id")
        self.assertEqual(database.connect_calls, 0)

    def test_executor_denies_when_durable_replay_store_is_unavailable(self):
        registry, policy, proposal, decision = tool_stack()
        self.assertTrue(decision.allowed)
        adapter = RecordingAdapter()
        executor = GuardedToolExecutor(
            registry,
            {"home.entity.read": adapter},
            policy_version=policy.policy_version,
            replay_protector=FailingReplayProtector(),
            clock=lambda: NOW,
        )
        result = executor.execute(proposal, decision)
        self.assertFalse(result.executed)
        self.assertEqual(result.reason_code, "replay_protection_unavailable")
        self.assertEqual(adapter.calls, 0)


if __name__ == "__main__":
    unittest.main()
