# ADR-0007: Private remote Android access

## Status

Accepted for the development environment.

## Context

HG-013 fixes the Android Node transport to the development Gateway at
`192.168.55.100:38443`. The Gateway certificate is also issued for that IP
address. This is intentional: the first Android milestone should prove one
narrow transport profile rather than introduce arbitrary remote endpoints.

A real phone, however, must eventually be able to reach the WTR PRO development
Gateway while the phone is on ordinary mobile Internet. Directly publishing the
Gateway on the public Internet would violate HearthGhost's network principles
and would unnecessarily widen the attack surface before the Node path has been
proven on physical hardware.

Changing the Android client to dial a public hostname would also require a new
server identity and certificate profile. Doing that merely to cross the Internet
would mix remote-access concerns into the Node protocol milestone.

## Decision

Remote Android development access uses a separate authenticated private-access
layer. The preferred development pattern is a private VPN overlay with the WTR
PRO host acting as a subnet router for the narrow development subnet that
contains `192.168.55.100`.

The Android application continues to dial:

```text
192.168.55.100:38443
```

The private-access layer is responsible only for making that private address
reachable from the phone. It does not terminate HearthGhost TLS, replace Node
mTLS, inject credentials into the application, or make the Gateway public.

This preserves the existing end-to-end Node security properties:

```text
Android Node
    |
    | private VPN route
    v
192.168.55.100:38443
    |
    | HearthGhost TLS 1.3 + ALPN + per-node mTLS
    v
Node Gateway
```

For the current development environment, Tailscale subnet routing is an
acceptable implementation of this private-access layer. Other authenticated
VPNs may be used if they preserve the same boundary.

## Required controls

- Do not port-forward TCP/38443 from the home router to the Internet.
- Advertise only the minimum subnet or host route needed for the development
  Gateway. Do not expose the entire home LAN merely for convenience.
- Tailnet/VPN policy must restrict the Android test device to the intended
  development route.
- The VPN identity is not a HearthGhost Node identity. A device that can route
  to the Gateway must still pass the normal Node certificate, trust, grant, and
  replay checks.
- The Gateway keeps its existing certificate identity for
  `192.168.55.100`; the VPN does not weaken or bypass HTTPS-style endpoint
  verification in the Android transport.
- Provider credentials remain server-side.
- Remote-access setup is operational infrastructure and must not place VPN auth
  keys, Node credentials, CA private keys, or other secrets in this repository.

## Development setup direction

On the Linux host that can route to the development subnet:

1. enable IP forwarding;
2. advertise the smallest route that reaches the Gateway through the private
   VPN overlay;
3. approve that advertised route in the VPN control plane;
4. restrict access policy to the designated Android test device or user;
5. verify the Android device can reach `192.168.55.100` only while the private
   VPN is active;
6. then perform the normal HG-014 enrollment and mTLS handoff.

For Tailscale specifically, current documentation uses
`tailscale set --advertise-routes=<CIDR>` after IP forwarding is enabled.
Android clients accept advertised subnet routes by default. Repository
documentation intentionally does not embed account-specific ACLs or reusable
Tailscale authentication keys.

## Consequences

### Positive

- no public listener is introduced;
- the Android Node transport and certificate profile remain unchanged;
- remote-access compromise does not automatically satisfy HearthGhost Node
  authentication or authorization;
- the same APK can be tested on home Wi-Fi and mobile Internet;
- HG-014 can remain focused on physical-device identity, enrollment, mTLS, and
  one text-only conversation.

### Negative

- the phone requires a separate VPN client while remote;
- WTR PRO must route the development subnet correctly;
- a second authorization plane exists and must be administered carefully;
- troubleshooting must distinguish VPN routing failures from HearthGhost TLS or
  Node-policy failures.

## Rejected alternatives

### Public router port-forward to the Gateway

Rejected because it directly exposes an early development listener to the
Internet and conflicts with HearthGhost's stated network policy.

### Reverse proxy or public TLS tunnel in front of the Gateway

Rejected for HG-014 because it adds another TLS identity and termination point
before the native mTLS path has been proven on the physical Android device.

### Make the Android Gateway endpoint freely configurable now

Deferred. Endpoint configurability is likely useful later, but it is not needed
to prove remote development access if the private VPN routes the existing
certificate-bound address. Arbitrary endpoint input would expand configuration,
validation, certificate, and support surface during a security-sensitive
milestone.
