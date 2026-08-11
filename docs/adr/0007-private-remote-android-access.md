# ADR-0007: Private remote Android access

## Status

Accepted for the development environment.

## Context

HG-013 fixes the Android Node transport to the development Gateway at
`192.168.55.100:38443`. The Gateway certificate is also issued for that IP
address. This is intentional: the first Android milestone should prove one
narrow transport profile rather than introduce arbitrary remote endpoints.

A real phone must eventually be able to reach the WTR PRO development Gateway
while the phone is on ordinary mobile Internet. Directly publishing the Gateway
on the public Internet would violate HearthGhost's network principles and widen
the attack surface before the Node path has been proven on physical hardware.

The phone may also be a normal daily-use device. Some payment, banking,
vehicle-control, projection, or vendor applications can behave incorrectly when
all device traffic or DNS is forced through a VPN. HearthGhost remote access
must therefore avoid requiring unrelated applications to use the same private
path.

## Decision

Remote Android development access uses a separate authenticated private-access
layer. The current preferred implementation is a Tailscale subnet route from the
Android phone to the narrow development subnet reachable through WTR PRO.

The Android application continues to dial:

```text
192.168.55.100:38443
```

The private-access layer is responsible only for making that private address
reachable from the phone. It does not terminate HearthGhost TLS, replace Node
mTLS, inject credentials into the application, or make the Gateway public.

The Android VPN must not be treated as an all-app policy requirement. When a
normal phone application is incompatible with VPN routing, configure Android
app-based split tunneling so that application bypasses Tailscale. Its traffic
and DNS then use the phone's ordinary network path while HearthGhost remains
able to use the private subnet route.

The desired traffic model is:

```text
HearthGhost Android client
        |
        | Tailscale private subnet route
        v
192.168.55.100:38443
        |
        | TLS 1.3 + ALPN + per-node mTLS
        v
Node Gateway

Unrelated VPN-sensitive app
        |
        | app-based split-tunnel exclusion
        v
ordinary Wi-Fi / mobile Internet
```

This is a routing separation, not a trust shortcut. Tailscale reachability does
not grant HearthGhost Node enrollment, trust, capability grants, or provider
credentials.

## Required controls

- Do not port-forward TCP/38443 from the home router to the Internet.
- Advertise only the minimum subnet or host route needed for the development
  Gateway. Do not expose the entire home LAN merely for convenience.
- Tailnet policy must restrict the Android test device or user to the intended
  development route.
- Do not require an exit node for HearthGhost remote access. The requirement is
  reachability to the private Gateway subnet, not Internet egress through home.
- Use Android app-based split-tunnel exclusions for applications that must not
  use Tailscale. Do not weaken HearthGhost TLS or Node policy to solve another
  application's VPN compatibility issue.
- The VPN identity is not a HearthGhost Node identity. A device that can route
  to the Gateway must still pass the normal Node certificate, trust, grant, and
  replay checks.
- The Gateway keeps its existing certificate identity for
  `192.168.55.100`; the VPN does not weaken or bypass endpoint verification in
  the Android transport.
- Provider credentials remain server-side.
- VPN authentication material, Node credentials, CA private keys, and other
  secrets must not be committed to this repository.

## Development setup direction

On WTR PRO or the Linux host that can route to the development subnet:

1. enable IP forwarding;
2. advertise the smallest route that reaches the Gateway through Tailscale;
3. approve the advertised route in the tailnet control plane;
4. restrict access policy to the designated Android test device or user;
5. do not configure an exit node merely for HearthGhost;
6. on the Android phone, exclude VPN-sensitive applications with Tailscale's
   app-based split-tunneling setting as needed;
7. verify those excluded applications still use the ordinary network path;
8. verify HearthGhost can reach `192.168.55.100` over mobile data;
9. then perform the normal HG-014 enrollment and mTLS handoff.

For Tailscale, Linux subnet routing uses IP forwarding and
`tailscale set --advertise-routes=<CIDR>`. Android app-based split tunneling can
exclude selected applications from Tailscale; excluded application traffic and
DNS bypass Tailscale. The inverse mode, where only selected applications are
forced through Tailscale, currently requires Android system policy/MDM, so the
development default is to exclude only applications that demonstrate a real
compatibility problem.

Repository documentation intentionally does not name account-specific ACLs,
reusable Tailscale authentication keys, or a permanent list of third-party
applications. Exclusions are operational device configuration and should remain
minimal.

## Consequences

### Positive

- no public HearthGhost listener is introduced;
- the Android Node transport and certificate profile remain unchanged;
- remote-access compromise does not automatically satisfy HearthGhost Node
  authentication or authorization;
- HearthGhost can use the private route without deliberately forcing unrelated
  applications through it;
- payment, vehicle, banking, or projection applications can be excluded if they
  demonstrate VPN incompatibility;
- HG-014 remains focused on physical-device identity, enrollment, mTLS, and one
  text-only conversation.

### Negative

- the phone still runs an Android VPN service while Tailscale is connected;
- exclusions must be maintained on a daily-use phone when incompatible apps are
  discovered;
- Android's convenient user-facing mode is exclusion-based rather than a strict
  HearthGhost-only include list;
- WTR PRO must route the development subnet correctly;
- a second authorization plane exists and must be administered carefully;
- troubleshooting must distinguish VPN routing failures from HearthGhost TLS or
  Node-policy failures.

## Rejected alternatives

### Public router port-forward to the Gateway

Rejected because it directly exposes an early development listener to the
Internet and conflicts with HearthGhost's stated network policy.

### Force all phone Internet traffic through a home exit node

Rejected. HearthGhost needs access to one private service path, not control over
all phone egress. Full-tunnel behavior creates unnecessary compatibility and
availability coupling with unrelated mobile applications.

### Reverse proxy or public TLS tunnel in front of the Gateway

Deferred for HG-014 because it adds another public-facing identity and boundary
before the native mTLS path has been proven on the physical Android device.

### Make the Android Gateway endpoint freely configurable now

Deferred. Endpoint configurability is likely useful later, but it is not needed
to prove remote development access if the private route preserves the existing
certificate-bound address. Arbitrary endpoint input would expand configuration,
validation, certificate, and support surface during a security-sensitive
milestone.

### Require only HearthGhost to use Tailscale through Android include mode

Not selected as the default because Android's Tailscale include-only package
policy currently requires device management/system policy. It remains a good
option for a managed dedicated device later.
