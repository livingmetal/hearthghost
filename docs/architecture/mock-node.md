# Mock Node E2E Boundary

HG-006 provides a harmless, outbound-only Mock Node for exercising the Node
security path before any physical or Android device exists.

```text
Mock Node
  -> TLS 1.3 mutual handshake
  -> bounded v1.0 Node Gateway frame
  -> certificate identity resolver
  -> credential lifecycle
  -> Node technical session
  -> replay sequence
  -> current trust
  -> advertised capability
  -> capability grant
  -> Gateway result (not execution authority)
```

The Mock Node declares only `display`, `speaker`, and `test.echo`. HG-006 uses
`test.echo` only to prove admission; it does not implement a display renderer,
audio output, sensor, media pipeline, Tool executor, or physical adapter.

## Lifecycle proved

The container integration test performs this ordered scenario through public
boundaries:

```text
known certificate + unknown Node -> session denied
administrator enrollment          -> untrusted, no grants
administrator trust + grant        -> session and test.echo admitted
duplicate sequence                 -> denied
capability revocation              -> next sequence denied
trust revocation                   -> next sequence denied
reconnect while active             -> new session, sequence restarts at 1
credential revocation              -> open session denied
reconnect after revocation         -> denied
```

The test administrator exists only inside the E2E harness and is not reachable
from the Mock Node or a network endpoint.

## Isolation

`socket.socketpair()` creates the connected channel in one isolated test
container. This avoids a host/LAN listener while retaining real TLS and framing.
The repository also provides a `mock-node` image target whose default `--check`
mode prints harmless metadata and exits. No certificate is included in that
image; connection mode requires explicit test-only certificate injection.

Build and inspect the Mock Node image:

```text
docker build --target mock-node -t hearthghost-mock-node:local .
docker run --rm --network none --read-only --cap-drop=ALL \
  --security-opt=no-new-privileges hearthghost-mock-node:local
```

## Deferred work

- separate-container private-network accept loop;
- production credential provisioning;
- Android implementation;
- any camera, microphone, location, media, or device capability;
- execution after Gateway admission.
