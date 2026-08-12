from pathlib import Path

path = Path("apps/assistant/src/adapters/postgres_schema.py")
content = path.read_text(encoding="utf-8")
anchor = '''    ),\n)\n\n\nclass PostgresSchemaError(RuntimeError):\n'''
if anchor not in content:
    raise RuntimeError("postgres migration tail anchor not found")
migration = '''    ),\n    Migration(\n        8,\n        "tool_policy_decision_replay_v1",\n        """\n        CREATE TABLE IF NOT EXISTS tool_policy_decision_consumptions (\n            decision_id UUID PRIMARY KEY,\n            consumed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP\n        );\n\n        CREATE INDEX IF NOT EXISTS idx_tool_policy_decision_consumptions_consumed_at\n        ON tool_policy_decision_consumptions(consumed_at);\n        """,\n    ),\n)\n\n\nclass PostgresSchemaError(RuntimeError):\n'''
content = content.replace(anchor, migration, 1)
path.write_text(content, encoding="utf-8")
