# ADR-0006: Rootless development Node Gateway runtime

## Status

Accepted

## Context

HG-012 needs the first real inbound Node Gateway listener on WTR PRO while
preserving the boundaries established by ADR-0001 through ADR-0005. The host is
`192.168.55.100` on the development LAN and the deployment must run as the
unprivileged `kaiser` user with rootless Podman. Health and administration must
not become LAN APIs.

A rootless bridge container does not own the host address
`192.168.55.100`. Binding that address inside the container therefore fails.
Binding the container listener to every container interface would work, but it
would make the intended ingress boundary less precise.

## Decision

Create a dedicated rootless, internal Podman bridge network with the fixed
container address `10.89.0.10`. The development Gateway binds only that literal
container address on TCP port `8443`. Podman publishes it only as
`192.168.55.100:38443`; wildcard host publication is forbidden. The network is
internal so the fake-LLM Core has no Internet route.

The listener accepts only TLS 1.3 with the `hearthghost-node/1` ALPN and a
client certificate issued by the development CA. It reuses the bounded,
length-prefixed Node and conversation protocols. A connection may carry one
ordered technical session and its text conversation. Malformed frames,
timeouts, protocol ambiguity, and authentication failures close the
connection.

The existing status HTTP surface remains on `127.0.0.1:8080` inside the
container and is not published. Node administration is a separate local CLI
operating on a restrictive persistent development-state file; no
administration or debug endpoint is added to the listener.

Development PKI and runtime state live under the `kaiser` account outside the
repository. The CA private key is never mounted into the runtime. The runtime
receives only its server key/certificate, the public CA certificate, and the
minimum writable state directory. Per-Node certificates bind to an explicitly
registered certificate fingerprint, and enrollment, trust, capability grants,
Node revocation, and credential revocation remain distinct administrator
actions.

The HG-012 runtime selects the fake LLM adapter explicitly. It receives no
provider credential and has no provider egress. A later live-provider slice
must isolate the provider secret and egress from this listener boundary rather
than adding the secret to the client or image.

## Consequences

Positive:

- the LAN exposure is one exact high port on one exact host address;
- neither the application listener nor the host publication uses a wildcard;
- the normal development Core stays offline and has no OpenAI credential;
- health, status, PKI authority, and administration remain outside the LAN
  protocol;
- registry and credential revocations are re-read from persistent state for
  every protected request.

Costs and constraints:

- the static rootless subnet and container address are development deployment
  inputs and must be checked for collision before creation;
- the file-backed store is a single-host development adapter, not a production
  datastore or multi-writer design;
- the server key is necessarily readable by the unprivileged Gateway process;
- live provider use needs an additional reviewed egress/secret boundary.

## Alternatives considered

### Bind `192.168.55.100` inside the container

Rejected because the host address is not assigned in the rootless container
network namespace.

### Bind `0.0.0.0` inside the container

Rejected because a fixed internal address is available and more accurately
expresses the intended ingress boundary.

### Host networking or a privileged/macvlan container

Rejected. Host networking weakens isolation, while rootless macvlan setup would
require broader host networking authority. Neither is necessary.

### Publish health or administration beside the Gateway

Rejected. Those surfaces are not Node protocol capabilities and would expand
the LAN attack surface.

## Security / Privacy impact

This adds one inbound attack surface, constrained to framed mTLS traffic from a
development-CA client certificate. TLS authentication still does not imply
enrollment, trust, grant, Policy approval, or node-local authorization. Private
Node keys and provider credentials never enter the Core container, repository,
image, build arguments, logs, or web client. Media remains denied.
