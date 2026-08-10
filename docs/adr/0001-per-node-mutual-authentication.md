# ADR-0001: Per-node mutual authentication

## Status

Accepted

## Context

HearthGhost needs to authenticate phones, tablets, and future embedded or robot
Nodes on a local-home network that is not inherently trusted. Each Node needs an
independent, revocable credential. Authentication must resist server and Node
impersonation, support offline household operation, and remain distinct from
Node trust, capability grants, current Policy, and node-local sensor gates.

HG-002 does not select a transport, implement TLS, create a CA, issue real
certificates, or select production secret storage. This ADR selects the preferred
identity proof for later transport implementation.

## Decision

Use a unique per-Node X.509 client certificate with mutual TLS as the preferred
authentication approach for a future Node Gateway transport.

The certificate is a credential, not the Node identity. A successful handshake
produces verified public evidence such as a credential identifier and Node
binding. The Node Gateway then consults its authoritative credential lifecycle
record and Node registry. Certificate validity alone never grants Node trust,
capabilities, Policy approval, device execution, or local camera/microphone use.

Each Node will also validate the Gateway's server certificate. A Node identity
is stable across address changes and credential rotation:

```text
Node N
  credential A (replaced)
  credential B (active)
```

The application lifecycle record remains authoritative for immediate local
revocation, including already-open sessions. A later PKI design may additionally
use certificate expiry, CRLs, or another mechanism, but transport-layer status
must not be the only revocation check.

HG-002 uses `session_id` plus a strictly increasing per-session `sequence` for
application replay admission. TLS record protection is necessary but does not
replace this action-level duplicate boundary.

This simple replay model requires requests to reach the application boundary in
sequence order. It does not require a particular ordered transport: an adapter
for a transport that can reorder delivery must serialize or restore request
order before admission. HG-002 deliberately does not add a sliding replay window.

TLS early data / 0-RTT is not allowed for the Node Gateway's command or
security-sensitive paths. It must not carry device actions, Policy changes,
camera or microphone requests, administrative commands, capability grants, or
session establishment. The initial implementation should disable 0-RTT for the
Node Gateway entirely. A future exception would require a separate ADR proving
that the data is read-only, idempotent, and harmless when replayed.

Standards and platform evidence:

- [TLS 1.3 RFC 8446, section 8](https://www.rfc-editor.org/rfc/rfc8446.html#section-8)
  states that 0-RTT data does not provide inherent replay protection and places
  replay handling on applications/servers.
- The official [Android Keystore documentation](https://developer.android.com/privacy-and-security/keystore)
  documents non-exportable key use and optional hardware-backed protection. A
  later Android implementation still needs to verify the actual device's key
  security level and client-certificate integration.

## Decision drivers

| Criterion | Per-Node X.509 / mTLS | Per-Node application signing key | Long-lived bearer/shared token |
| --- | --- | --- | --- |
| Unique Node identity | Strong when every Node receives a distinct certificate and registry binding | Strong with distinct public keys | Weak if shared; per-Node tokens improve attribution but remain bearer credentials |
| Independent revocation | Certificate plus application lifecycle record | Public-key lifecycle record | Possible per token, impossible to scope when one token is shared |
| Rotation | Established certificate replacement patterns; Node binding remains stable | Straightforward key replacement but protocol-specific | Token replacement is simple, but secure delivery and overlap remain difficult |
| Stolen credential impact | Scoped to one Node if credentials are unique; private key protection still matters | Scoped to one Node; signatures may support message-level proof | Bearer possession is sufficient; accidental copying/logging is a high risk |
| Server impersonation resistance | Built into mutual certificate validation | Requires a separate authenticated server channel or reciprocal signing design | Depends entirely on transport server authentication |
| Node impersonation resistance | Strong proof of private-key possession | Strong proof of private-key possession | Weaker operationally because no proof-of-possession protocol beyond presenting the secret |
| Replay resistance | TLS protects records in-session; application sequence is still required | Can bind signatures to session/sequence, but canonicalization and protocol design are substantial | Requires separate nonce/sequence machinery and is easy to misuse |
| Implementation complexity | Medium to high, but standard TLS stacks own the cryptographic protocol | High because HearthGhost must define signed-message canonicalization and session binding | Low initially, with substantial lifecycle and leakage risk |
| Android feasibility | Feasible with a native shell and Android Keystore; browser client-certificate UX is poor | Feasible with Keystore and application protocol code | Easy to prototype and easy to leak through app storage/logs |
| Web/PWA feasibility | Browser-managed client certificates are operationally awkward | WebCrypto key persistence/export policy varies and needs a protocol | Technically easy but unacceptable as a shared architecture |
| Robot/embedded feasibility | Mature TLS stacks are widely available; provisioning remains work | Feasible, especially on constrained devices, but custom protocol work grows | Easy but weak lifecycle and theft posture |
| Offline/local-home operation | Works with a household CA and local registry; no public CA or Internet required | Works locally | Works locally |
| WTR PRO compatibility | Routine CPU and memory cost for a modest number of Nodes | Routine crypto cost, but more application code | Lowest computational cost |
| Operational recovery | Requires documented re-enrollment, CA backup, expiry, and replacement procedures | Requires equivalent key recovery/re-enrollment procedures | Easy reset, but shared-token rotation disrupts every Node |
| Dependency/PKI burden | Highest; CA lifecycle and platform TLS integration must be operated correctly | Medium; crypto libraries plus canonical signed-message protocol | Lowest initially, highest risk of unsafe permanence |

## Consequences

Positive:

- compromise or theft of one Node credential does not authenticate every Node;
- both Gateway and Node receive strong peer authentication;
- standard TLS implementations provide mature cryptographic primitives;
- Node address, hostname, area, and user identity remain outside the credential's
  logical identity semantics;
- application revocation can invalidate an open session without waiting for
  certificate expiry.

Costs and constraints:

- a household CA or equivalent enrollment authority, certificate issuance,
  renewal, secure backup, and recovery procedures are required later;
- Android Keystore integration and certificate enrollment require a native
  boundary; a pure PWA client becomes less attractive for persistent Nodes;
- certificate subject fields must not become the only authoritative registry;
- expiry and rotation failures can reduce availability, and security still
  requires fail-closed behavior;
- TLS libraries and configuration require separate dependency and hardening
  review.

## Alternatives considered

### Per-node asymmetric application signing key

This is a credible second choice and may later complement mTLS where
message-level end-to-end proof is required. It provides per-Node proof of
possession and can bind a signature to session and sequence. It was not selected
as the primary approach because HearthGhost would need to define canonical
message serialization, challenge/session binding, key discovery, downgrade
handling, server authentication, and replay behavior at the application layer.
That is more custom security protocol than HG-002 can justify.

### Long-lived bearer or shared token

Rejected as architecture. A shared token destroys independent attribution and
revocation. Even distinct per-Node bearer tokens are replayable secrets whose
possession is sufficient for impersonation and which are easily copied into
logs, configuration, or backups. A short-lived token issued after stronger
authentication could later be a session implementation detail, but it is not a
Node identity credential and must not replace per-Node proof of possession.

## Security / Privacy impact

mTLS reduces unauthenticated and peer-impersonation risk but does not authorize
an action. The required order remains credential verification, lifecycle and
revocation check, Node resolution, Node trust, replay admission, capability
grant, Policy/confirmation where applicable, Executor/adapter checks, and any
node-local sensor or physical-safety gate.

Private keys, certificates, transport proof, and bearer material must not enter
generic contracts, fixtures, logs, or audit metadata. Only public identifiers,
status, timestamps, and correlation metadata belong there.

A compromised Core that possesses a valid server certificate still cannot
legitimately bypass a Node's local camera or microphone gate. mTLS authenticates
the peer; it does not make the peer universally trustworthy.

## Deferred implementation decisions

- CA topology, root-key storage, issuance, renewal, and recovery;
- certificate profile, key algorithm, lifetime, and subject/extension mapping;
- Android Keystore and embedded secure-storage integration;
- production listener and application framing;
- bounded rotation overlap, if operational evidence requires one;
- persistent revocation and replay storage technology;
- whether application-level signatures are needed in addition to mTLS.
