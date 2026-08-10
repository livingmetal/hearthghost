# Node Identity, Credential, Session, and Replay Boundary

## Purpose

The Node Gateway must answer several security questions without treating them
as synonyms:

```text
credential proof verified
  != logical Node is trusted
  != capability is granted
  != request is currently admissible
  != Policy allows an action
  != node-local sensor gate allows use
```

HG-002 implements a transport-neutral application boundary. It opens no
listener and performs no cryptography. HG-004 supplies a standard-library mTLS
credential adapter while preserving that domain separation; the adapter still
opens no listener.

## Domain records

### Node identity

`node_id` is the stable logical identifier. It is not an IP address, hostname,
room, user identity, transport connection, or credential identifier. A Node may
move networks or rotate credentials without changing `node_id`.

Node trust uses the existing states:

```text
untrusted
pending_approval
trusted
restricted
revoked
```

Only `trusted` admits a protected capability request in HG-002. This conservative
rule avoids inventing permissions for `restricted`; a later task must explicitly
define any restricted-operation allowlist before it can allow one.

The v1.0 Node identity contract coupled one credential's status to Node security
state, and its capability contract duplicated Node security state. Rewriting
immutable v1 contracts would violate repository versioning, so they are retained
for traceability. Node Gateway code uses Node identity and capability v2 plus the
separate credential lifecycle contract.

These are independently versioned schemas, not one Node protocol release.
Identity `v2.0`, capabilities `v2.0`, and credential `v1.0` each state the major
version of that record only. A consumer must validate support for each contract
it receives and must not infer a credential version from an identity directory.

### Credential

A credential record contains only public lifecycle metadata:

```text
credential_id
node_id
credential_type
issued_at
expires_at (optional)
revoked_at (when revoked)
replacement_credential_id (when replaced)
status = active | revoked | expired | replaced
```

`credential_type` is an open technology-neutral identifier. Contracts and
domain records contain no private key, certificate body, bearer token, or proof.

Only an internally consistent `active` credential that has been issued and has
not expired is valid. Revoked, expired, and replaced credentials fail closed.
Missing lifecycle state, an unavailable repository/clock, mismatched Node
binding, naive timestamps, and contradictory fields also fail closed.

Revocation is checked during initial authentication, session opening, and every
protected request. An already-open session therefore stops working when its
credential becomes revoked or replaced.

### Rotation

Rotation creates a new credential for the same `node_id`:

```text
credential A: replaced -> replacement_credential_id = credential B
credential B: active   -> same node_id
```

The old credential is invalid as soon as its authoritative state becomes
`replaced`; sessions bound to it fail their next request. HG-002 does not create
an automatic overlap period. If deployment evidence later requires overlap, it
must be bounded, explicit, audited, and added through a reviewed decision rather
than inferred from both credentials being present.

### Capability state

Advertisements and grants are stored independently:

```text
advertised: camera.snapshot, speaker.play
granted:    speaker.play
```

Advertising is not authorization. A protected request must name a capability
that is both currently advertised and explicitly granted. Authentication and
Node trust do not populate the grant set.

Advertisements for `camera.snapshot`, `camera.stream`, `microphone`, and
`microphone.session` must declare a node-local authorization requirement. A
record that disables that requirement is ambiguous and denied.

## Authentication and request flow

The implemented ordering is:

```text
opaque transport presentation
  -> credential authenticator (HG-004 mTLS adapter; no custom crypto)
  -> verified credential_id + node_id
  -> authoritative credential lifecycle / expiry / revocation
  -> credential-to-Node binding
  -> Node registry and trust-state validity
  -> authenticated technical session
  -> same currently verified transport credential bound to each request
  -> current credential and Node state re-check
  -> replay sequence admission
  -> trusted Node check
  -> advertised capability check
  -> granted capability check
  -> Node Gateway admission result
```

An admission result is not a Policy Decision and must not be sent directly to a
device executor as authority. Tool or device action flows still require current
Policy, risk, confirmation, Executor, and adapter checks. Camera, microphone,
and future sensitive physical capabilities additionally require a node-local
gate. A compromised Core cannot convert Gateway authentication into a local gate
allow.

## Session separation

These objects remain distinct:

```text
Node identity
Credential
Transport connection
Authenticated Node session
Conversation session
```

HG-002 models only the authenticated Node session. It binds one server-issued
`session_id` to one `node_id` and one `credential_id`, with an opening and expiry
time. Every request and session close must also carry current credential evidence
from the trusted transport authenticator that matches that binding; `session_id`
is never a bearer credential. A transport can reconnect only through future
transport rules; it does not silently preserve a Node session. A Node session
may remain open while the conversation state is `sleeping` and no conversation
session exists.

## Replay protection

HG-002 selects the smallest coherent application mechanism:

```text
session_id + strictly increasing positive sequence
```

Properties:

- replay scope: one authenticated Node session;
- duplicate responsibility: the Node Gateway's replay store atomically records
  the highest accepted sequence;
- acceptance: a sequence must be greater than the stored value;
- ordering: duplicates and older/out-of-order values are denied;
- delivery requirement: requests must reach the Gateway admission boundary in
  sequence order. An unordered or concurrent transport adapter must serialize or
  restore that order before admission; otherwise a legitimate late request is
  denied. No transport protocol is selected by this requirement;
- consumption: after credential and session validation, a sequence is consumed
  before trust and capability evaluation, so a denied request cannot become
  valid later after grants change;
- clock dependency: none for replay ordering; trusted time is used separately
  for credential and session expiry;
- session restart: a new authenticated session receives a new, globally unique
  server-issued `session_id` and begins independent sequence state. Session
  storage must reject rather than overwrite a previously used identifier. The
  old session is closed or expires, so its messages remain invalid;
- isolation: replay state is keyed only after session lookup has bound the
  globally unique `session_id` to exactly one Node and credential. One session's
  highest sequence therefore cannot advance another session's state, including
  a session belonging to another Node;
- persistence: state must survive transport reconnects for the lifetime of the
  logical Node session. Process-crash persistence is deferred to session-store
  selection; after uncertain loss, affected sessions must be invalidated rather
  than resetting their sequence;
- failure: unknown session, unavailable replay state, duplicate, older value,
  malformed sequence, or ambiguous state is denial.

This design does not require a nonce or request timestamp for replay admission.
`request_id` remains correlation metadata and is not the replay primitive.
Strictly increasing admission intentionally favors a small fail-closed state
machine over accepting unordered delivery. A sliding replay window is deferred
unless a concrete transport requirement later proves it necessary.

TLS 0-RTT is denied as specified by ADR-0001 because early data can be replayed
before the application sequence boundary can safely establish session state.

## Public implementation boundary

`apps/assistant/src/modules/node_security.py` provides:

- credential, Node, session, request, and result domain types;
- `authenticate_node(...)`;
- `open_session(...)` and `close_session(...)`;
- `admit_request(...)`, which means Gateway admission only;
- fail-closed consistency validation.

`apps/assistant/src/ports/node_gateway.py` defines ports for:

- credential proof authentication;
- credential lifecycle storage;
- Node registry storage;
- Node session storage;
- atomic replay tracking;
- trusted server time.

Adapters must not turn verifier exceptions, missing state, storage errors, or
clock errors into success. Implementations must avoid logging opaque credential
presentations.

## Deferred work

- network listener, connection limits, and media framing;
- production PKI and certificate enrollment;
- persistent repository and replay-store implementations;
- persistent administration store and administrator identity implementation;
- Policy Decision binding to a device action;
- runtime audit adapter integration;
- node-local camera/microphone gate implementation;
- conversation sessions and media transport.
