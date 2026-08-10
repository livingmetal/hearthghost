# Security Boundary Tests

`planned-denial-cases.json` is the acceptance-test inventory for future
security-sensitive implementations. Every case is deliberately marked
`not_implemented` in HG-001 because no Policy, node authentication, Privacy
Gateway, or tool executor exists yet.

When a later task implements a boundary:

1. create an executable test through the public boundary rather than mocking the
   policy result away;
2. prove the denial behavior, including unavailable dependency/state cases;
3. update only the covered case status and link it to the executable test;
4. keep fixtures free of real credentials and household media.

An allow-path test never replaces the corresponding denial tests.
