# Security Boundary Tests

`planned-denial-cases.json` is the acceptance-test inventory for
security-sensitive implementations. HG-002 promotes Node identity, credential,
trust, capability, session, and replay cases to `implemented` and links each to
an executable public-boundary test. Policy, Privacy Gateway, node-local sensor
gate, and tool-executor cases remain explicitly `not_implemented`.

HG-003 adds executable denial coverage for authenticated-Node privilege
confusion, automatic trust, stale administration revisions, unadvertised grants,
and non-atomic privileged audit writes.

HG-004 adds ephemeral-certificate integration coverage for TLS downgrade and
profile enforcement, missing client certificates, server hostname mismatch,
unknown certificate mappings, resolver failure, and the rule that successful
mTLS authentication does not grant Node authority. The fixtures are generated
at test time and never committed.

HG-006 extends this into a framed Mock Node lifecycle. One E2E scenario proves
unknown-Node denial, explicit enrollment/trust/grant, replay rejection,
capability and trust revocation, credential revocation, and reconnect behavior.
The Mock Node cannot administer itself and has no media or physical capability.

When a later task implements a boundary:

1. create an executable test through the public boundary rather than mocking the
   policy result away;
2. prove the denial behavior, including unavailable dependency/state cases;
3. update only the covered case status and link it to the executable test;
4. keep fixtures free of real credentials and household media.

An allow-path test never replaces the corresponding denial tests.
