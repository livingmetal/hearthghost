# Tests

This directory contains cross-module contract validation and the structure for
future integration, security-boundary, and end-to-end tests that do not naturally
belong beside a single module.

Security-sensitive functionality must test denial paths as well as success paths.

Important examples include:

```text
unauthorized camera request -> denied
revoked node credential -> denied
unknown device -> denied
LLM Hard Policy change request -> denied
critical tool without confirmation -> denied
cloud image upload under default policy -> denied
policy service unavailable -> sensitive action denied
```

The test suite must not use real household secrets, private media, addresses, access tokens, or production credentials.

When a task changes a trust boundary, contract, or security policy, tests should demonstrate that the intended negative cases remain closed.

## Foundation validation

Run the dependency-free foundation suite from the repository root:

```text
python -m unittest discover -s tests -p "test_*.py"
```

`contracts/` verifies the structure and selected security invariants of the JSON
Schemas. `security/` records required denial cases and links `implemented`
entries to executable boundary tests. Deferred cases remain
`not_implemented`; planning entries never substitute for application behavior.
Each implementation task must promote only the cases it proves through the
public boundary.

See `../AGENTS.md` and `../docs/security/threat-model.md`.
