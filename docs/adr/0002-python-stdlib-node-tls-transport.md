# ADR-0002: Python standard-library TLS for the initial Node transport

## Status

Accepted

## Context

ADR-0001 selects unique per-Node X.509 credentials and mutual TLS while keeping
authentication separate from Node trust and authorization. HG-004 needs the
smallest concrete adapter around the existing Node Gateway ports. It must not
invent cryptography, select production PKI operations, or open a network
listener before the Core runtime has an explicit listener policy.

The current repository test image is Python 3.13 on Debian Bookworm.
Python's `ssl` module delegates TLS and certificate validation to OpenSSL. The
WTR PRO target can run this maintained container without specialized hardware.

## Decision

Use Python 3.13's standard-library `ssl.SSLContext` and its linked OpenSSL
implementation for the initial Node transport adapter.

The profile is deliberately narrow:

- TLS 1.3 is both the minimum and maximum protocol version;
- the server uses `CERT_REQUIRED` and a configured Node-client trust store;
- the client validates the Core certificate and hostname;
- both peers must negotiate ALPN `hearthghost-node/1`;
- server TLS 1.3 session tickets are disabled (`num_tickets = 0`), so the
  initial adapter does not resume a transport identity or accept early data;
- client authentication occurs in the initial handshake; post-handshake
  authentication is not enabled;
- the adapter accepts an already-connected socket and owns no bind address,
  listener, port, framing, or deployment policy;
- only a certificate negotiated with the exact configured server context may
  reach the certificate-to-credential resolver.

The TLS stack validates the certificate chain. A dedicated port maps the
verified public DER certificate to `credential_id` and `node_id`. The existing
Node Gateway then rechecks authoritative credential lifecycle, Node state,
session binding, replay sequence, trust, advertisement, and capability grant.
TLS success is therefore authentication evidence only.

Automated integration tests create a two-day, clearly test-only CA and leaf
certificates in an ephemeral temporary directory by invoking the image's
OpenSSL CLI. The private keys are deleted with that directory, never committed,
never persisted outside the isolated test container, and do not define the
future production CA or certificate profile.

## Dependency assessment

### Maintenance and long-term viability

Python 3.13 and OpenSSL are maintained upstream components already present in
the selected base image. The adapter adds no Python package and no separate TLS
framework. Python documents `SSLContext`, mandatory client certificates, TLS
version bounds, ALPN, and server ticket controls as supported APIs.

### License

- Python software and documentation use the Python Software Foundation License
  Version 2.
- OpenSSL 3.0 and later use the Apache License 2.0.

No third-party source is vendored. Image-distribution license inventory remains
a future release-engineering concern; this ADR records the evidence supporting
the implementation choice.

### Attack surface

Using the language/runtime TLS binding avoids custom record protection,
certificate parsing, signature code, or a HearthGhost-specific cryptographic
protocol. Restricting the adapter to connected sockets also keeps listener,
HTTP/WebSocket, public routing, and application-message parsing out of HG-004.
The OpenSSL/Python security update lifecycle becomes part of image maintenance.

### Android compatibility

The wire security primitive is standard TLS 1.3 with X.509 client and server
authentication plus ALPN; it does not require Python on a Node. A future native
Android Node can use the platform TLS and Keystore facilities described in
ADR-0001. Browser-managed client certificates remain deliberately unsupported
as the primary persistent-Node mechanism.

### WTR PRO suitability

The target AMD64 Linux server can run the existing slim Python container and
OpenSSL without GPU or privileged-container requirements. Expected household
Node scale does not justify a separate TLS proxy or service mesh. Performance
measurement can occur only if an observed load later requires it.

## Consequences

Positive:

- mutual peer authentication uses mature TLS primitives already shipped in the
  runtime;
- TLS configuration is explicit and fail closed;
- no new package, framework, listener, service, or custom cryptography is added;
- the same client adapter can later support an isolated mock Node;
- certificate verification remains cleanly separated from application
  credential lifecycle and authorization.

Costs and constraints:

- Python and OpenSSL security updates must be applied through base-image
  maintenance;
- persistent certificate-to-credential resolution is still required;
- disabling tickets gives up resumption performance until a reviewed design can
  preserve revocation and replay invariants;
- TLS protects the channel but does not define application framing or ordering.

## Alternatives considered

### Third-party Python TLS or networking framework

Rejected for this milestone. The standard library supplies the required TLS
primitive, and a framework would add dependencies and listener/application
semantics before they are needed.

### TLS-terminating reverse proxy

Deferred. It would create another certificate-verification and identity-forwarding
boundary. HG-004 can enforce mTLS directly without trusting headers or a proxy
network path.

### Custom application signatures or pre-shared keys

Rejected as the transport authentication mechanism for the reasons in ADR-0001.
They would either create custom security protocol work or weaker bearer-secret
semantics.

## Security / Privacy impact

Certificate absence, invalid chains, hostname mismatch, TLS downgrade, missing
ALPN, unknown certificate mapping, and resolver failure all deny authentication.
An authenticated but untrusted Node can establish only the narrow technical
session already allowed by the Node Gateway; protected capability admission
remains denied. Policy approval, device execution, and node-local camera or
microphone authorization remain separate and are not implemented here.

## Evidence reviewed

Reviewed 2026-08-11:

- [Python 3.13 `ssl` documentation](https://docs.python.org/3.13/library/ssl.html)
- [Python 3.13 license](https://docs.python.org/3.13/license.html)
- [OpenSSL source and release information](https://www.openssl-library.org/source/)
- [Android network protocol security](https://developer.android.com/privacy-and-security/security-ssl)
- [Android Keystore](https://developer.android.com/privacy-and-security/keystore)

The validation image reported Python-linked OpenSSL 3.0.20. That observation is
test evidence, not a production version pin.

## Deferred decisions

- production CA topology, certificate profile, issuance, storage, and recovery;
- persistent certificate-to-credential resolver;
- network listener address, port, accept-loop, and connection limits;
- application framing, request size limits, and ordered delivery integration;
- production certificate revocation distribution beyond the authoritative
  application lifecycle check;
- Android TLS/Keystore implementation.
