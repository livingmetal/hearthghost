# Tests

This directory will contain cross-module, integration, security-boundary, and future end-to-end tests that do not naturally belong beside a single module.

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

See `../AGENTS.md` and `../docs/security/threat-model.md`.
