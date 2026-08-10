# Mock Node

This test-only Node exercises the same TLS client and framed Node Gateway
protocol intended for future physical Nodes. Its complete capability set is:

```text
display
speaker
test.echo
```

It has no sensor or physical-control implementation. The Mock Node accepts no
inbound connection, stores no credential in the repository, and cannot enroll,
trust, grant, revoke, or authorize itself.

`python -m apps.mock_node.src.client --check` prints non-sensitive identity and
capability metadata without connecting. A real integration run must inject
ephemeral test-only certificate paths and a private test endpoint explicitly.
