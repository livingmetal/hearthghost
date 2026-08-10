# HG-INTEGRATION-001 Security and Architecture Integration Review

## Scope

This review evaluates HG-003 through HG-006 as one security path. It does not
add product functionality, a listener, production credentials, device
execution, media handling, or a permissive Policy path.

## Integrated path

```text
test-only Node certificate
  -> TLS 1.3 mutual authentication
  -> certificate-to-credential evidence
  -> credential lifecycle and Node binding
  -> technical Node session
  -> replay sequence
  -> current Node trust
  -> advertised capability
  -> granted capability
  -> Gateway admission only
```

Node enrollment, trust, grants, and revocation remain behind the independently
authenticated administration boundary. Registry mutation and its privileged
audit event are one atomic store operation. Policy, device execution, and
node-local sensor authorization remain separate and are not implemented by this
path.

## Review results

| Area | Result |
| --- | --- |
| Enrollment | Explicit administrator action; creates an untrusted Node with no grants. |
| Trust | Only `trusted` admits a protected request; `restricted`, pending, untrusted, and revoked states deny. |
| Grants | Advertisement and grant are independent; revocation affects the next request. |
| Administration concurrency | Expected revisions and atomic compare/update reject stale mutations. |
| Audit | A state mutation is not visible unless its metadata-only audit event is stored atomically. |
| Transport | Exact TLS 1.3, mutual certificates, hostname validation, and ALPN are required. |
| Credentials | Lifecycle is rechecked for every protected request; revocation invalidates open sessions. |
| Node revocation | Revocation denies the next request and future session opening. |
| Replay | Strictly increasing per-session sequence is consumed before trust/grant evaluation. |
| Sessions | Technical Node sessions are distinct from future conversation sessions. |
| Core | Missing transport, administrator authority, and Policy rules use explicit deny-only adapters. |
| Containers | Test/Core/Mock Node images run non-root without host networking, ports, volumes, devices, or added capabilities. |
| Contracts | Message/result schemas match the bounded v1.0 frame and preserve proposal/admission versus execution semantics. |

## Mock Node equivalence

The Mock Node uses the same client-side TLS profile and the same framed Node
Gateway protocol intended for a future Android Node. The server path is the
production-shaped path: `MutualTlsCredentialAuthenticator`, credential store,
Node registry, session store, replay boundary, and `NodeGatewayProtocol`.

The only Mock-specific pieces are the platform shell, the test certificate
fixture, and its harmless fixed capability declaration. The test administrator
is held by the E2E harness and is never reachable through the Mock Node channel.
There is no `test_mode` switch in the Gateway, no automatic enrollment or
trust, and no Mock-only admission branch.

## Findings and corrections

No established invariant requires redesign. The implementation review found no
trust, administration, transport, replay, or execution bypass. It did identify
two integration-level negative coverage gaps: the real framed mTLS path did not
directly demonstrate capability denial for an authenticated-but-untrusted Node,
and it did not directly demonstrate terminal Node revocation against an open
session plus reconnect. HG-INTEGRATION-001 adds both scenarios.

Searches for TODO, FIXME, debug bypasses, permissive test modes, and secret-like
shortcuts found no implementation marker requiring correction. The currently
documented production omissions remain deliberate and fail closed.

## Deferred decisions

- production PKI, certificate provisioning, and Android secure-key storage;
- a private Core Node listener with resource and concurrency limits;
- persistent registry, audit, session, and replay storage;
- administrator identity and management transport;
- Policy allow rules, Tool execution, and node-local media gates;
- conversation, character, and provider integration added by later milestones.
