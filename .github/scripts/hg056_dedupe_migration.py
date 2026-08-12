from pathlib import Path

path = Path("apps/assistant/src/adapters/postgres_schema.py")
content = path.read_text(encoding="utf-8")
block = '''    Migration(\n        8,\n        "tool_policy_decision_replay_v1",\n        """\n        CREATE TABLE IF NOT EXISTS tool_policy_decision_consumptions (\n            decision_id UUID PRIMARY KEY,\n            consumed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP\n        );\n\n        CREATE INDEX IF NOT EXISTS idx_tool_policy_decision_consumptions_consumed_at\n        ON tool_policy_decision_consumptions(consumed_at);\n        """,\n    ),\n'''
if content.count(block) != 2:
    raise RuntimeError(f"expected exactly two replay migration blocks, found {content.count(block)}")
first = content.find(block)
second = content.find(block, first + len(block))
content = content[:second] + content[second + len(block):]
path.write_text(content, encoding="utf-8")
