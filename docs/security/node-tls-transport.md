# Secure Node Transport Boundary

HG-004 implements the mTLS adapter proposed by ADR-0001 without adding a network
listener or production PKI.

```text
already-connected socket
  -> TLS 1.3 mutual handshake
  -> exact ALPN profile
  -> verified peer certificate
  -> certificate-to-credential resolver
  -> VerifiedCredential
  -> Node Gateway lifecycle / Node / session / replay checks
```

These states remain separate:

```text
TLS certificate verified
  != certificate is registered
  != credential is active
  != Node is trusted
  != capability is granted
  != Policy allows an action
  != device or local sensor gate allows execution
```

## Fail-closed transport profile

The server requires TLS 1.3, a client certificate chaining to its configured
test/runtime trust store, and ALPN `hearthghost-node/1`. The Node client requires
the same protocol profile and validates the Core certificate hostname. Session
tickets are disabled on the server context, and the adapter does not enable
post-handshake authentication or early data.

The credential authenticator accepts only an `SSLSocket` negotiated with the
exact trusted server context. It retrieves the TLS-verified public DER peer
certificate and delegates only the certificate-to-credential mapping. Missing,
unknown, malformed, wrong-context, or failed resolver state never becomes a
credential identity. Resolver exceptions propagate to the Node Gateway, which
maps them to `authenticator_unavailable` and denies the request.

## Listener and protocol separation

The adapter wraps an already-connected socket. It does not:

- bind or listen on an address;
- expose a container port;
- select TCP routing, HTTP, WebSocket, gRPC, MQTT, or QUIC;
- parse Node application messages;
- serialize concurrent requests before replay admission;
- issue certificates or retain private keys.

The HG-005 Core runtime must make listener scope and application framing
explicit. A transport that allows concurrent or reordered application messages
must deliver them in sequence order before calling the replay boundary.

## Test credential handling

Integration tests generate an ephemeral test-only CA, Core certificate, known
Node certificate, and unknown Node certificate. They use no real identity,
expire after two days, exist only in an OS temporary directory, and are removed
after the test class completes. No certificate, private key, model, binary, or
production credential is stored in the repository.

## Deferred production work

- CA and certificate lifecycle operations;
- persistent certificate binding lookup;
- Core listener and connection resource limits;
- Android client integration;
- production audit sink and transport metrics.
