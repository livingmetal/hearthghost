# ADR-0004: Mock Node and bounded Node Gateway framing

## Status

Accepted

## Context

HG-006 must prove the Node lifecycle end to end through the same authentication,
session, replay, trust, and capability boundaries intended for physical Nodes.
The milestone may use test certificates but cannot create production PKI,
camera/microphone behavior, a LAN listener, or an administration bypass.

HG-004 supplies TLS for connected sockets, but application messages on that
channel were deferred. The Mock Node needs a small versioned wire contract to
open and close a technical session and submit a protected capability request.

## Decision

Add a test-only outbound Mock Node with exactly these capabilities:

```text
display
speaker
test.echo
```

The Mock Node uses the HG-004 TLS client adapter and cannot enroll, trust, grant,
revoke, or authorize itself. It implements no inbound listener, sensor, media,
Tool execution, physical control, or Policy function.

Use a four-byte unsigned network-order length followed by UTF-8 JSON for the
initial Node Gateway application frame. Frames are limited to 16 KiB. The v1.0
request contract supports only:

```text
session.open
capability.request
session.close
```

Each request has a UUID correlation ID. A capability request carries the
authenticated technical `session_id`, strictly increasing positive 63-bit
`sequence`, and capability name. Message-type fields are exact; unknown fields,
invalid versions, invalid UTF-8/JSON, truncation, zero length, and oversized
frames fail closed.

The response says only `accepted` or `denied` with a reason code and optional
Node/session correlation. An accepted response is the result of the named
Gateway operation only. It is never a Policy Decision, Tool authorization, or
device execution permission.

The E2E harness uses `socket.socketpair()` to isolate both peers without creating
a network listener. Both sides still perform the real TLS 1.3 mutual handshake,
certificate-to-credential resolution, framing, and public Gateway calls. Test
certificates are generated in an ephemeral container temporary directory and
deleted after the test class.

## Consequences

Positive:

- the full Node security lifecycle is executable without a physical device;
- application replay state is exercised across an actual framed mTLS channel;
- Mock Node and Core code cannot silently exchange arbitrary dictionaries;
- malformed or oversized frames are bounded before domain dispatch;
- no port, listener, media path, production credential, or administration API is
  introduced;
- the Mock Node has its own non-root image target and can later be attached to an
  explicitly isolated integration network.

Costs and constraints:

- JSON framing is not yet a high-throughput media transport;
- one connection handler currently processes messages in call order, matching
  the replay boundary's ordering requirement;
- there is no accept loop, connection concurrency policy, rate limit, or
  persistent session/replay state;
- `display` and `speaker` are declarations only; HG-006 executes no output.

## Alternatives considered

### Plain method calls into Node Gateway

Rejected for the E2E path because they would bypass TLS presentation and wire
parsing. Unit tests still call domain boundaries directly where appropriate.

### Commit test certificates

Rejected. Ephemeral generation avoids reusable credentials and prevents test
keys from becoming accidental operational PKI.

### Bind a Core listener on the development/runtime host

Rejected for HG-006. A socket pair proves the connected-socket security path
without crossing the production network-exposure STOP GATE. A future accept loop
requires explicit connection limits, private network design, and deployment
review.

### Add media or physical capabilities to the Mock Node

Rejected. They add privacy and safety semantics unrelated to proving Node
identity, administration, replay, and revocation.

## Security / Privacy impact

The integration proves:

- a TLS-valid credential for an unknown Node is denied;
- enrollment starts untrusted with no grants;
- trust and grants require the independent administration boundary;
- duplicate sequence is denied;
- revoking capability or trust affects an open technical session;
- reconnect creates a distinct technical session and replay scope;
- credential revocation invalidates the open session and subsequent reconnect;
- plaintext channels and oversized frames are rejected.

No household identity, secret, image, audio, video, location, device command, or
cloud data is processed.

## Deferred decisions

- Core network accept loop and private Node network;
- connection concurrency, rate limits, and resource accounting;
- production certificate resolver and PKI;
- persistent session/replay state and restart invalidation;
- media/binary transport;
- physical or Android Node implementation.
