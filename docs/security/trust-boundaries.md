# Trust Boundaries

## Principle

HearthGhost does not treat "inside the house" or "on the LAN" as synonymous with trusted.

The architecture should support logical separation between at least these zones:

```text
Trusted User Zone
AI Core Zone
Sensor / Node Zone
IoT Zone
Guest / Untrusted Zone
Internet / External Providers
```

## Trusted User Zone

Examples:

- personal phones
- administrative PC
- authenticated management devices

These devices may be allowed to administer HearthGhost, but routine AI nodes should not automatically receive access to this zone.

## AI Core Zone

Contains the WTR PRO server and security-sensitive HearthGhost services such as:

- Core / Orchestrator
- Policy
- Registry
- Memory
- Node Gateway
- Privacy Gateway
- Audit
- approved adapters

Services inside this zone are still not universally trusted. Credentials and egress should be scoped per service where practical.

## Sensor / Node Zone

Contains dedicated phones/tablets and future sensing nodes.

Expected posture:

```text
Node -> authenticated outbound connection -> Node Gateway
Node -> Trusted User Zone: DENY by default
Node -> IoT Zone: DENY by default
Node -> Internet: DENY or tightly restricted where practical
```

Nodes should not expose generic inbound camera or microphone services.

## IoT Zone

Contains Home Assistant-connected smart-home devices and other IoT products. IoT devices should not be trusted to initiate arbitrary access into the AI Core or Trusted User zones.

Home Assistant acts as an integration boundary; the LLM does not directly hold Home Assistant credentials.

## Guest / Untrusted Zone

Guest devices and unknown network clients have no implicit access to HearthGhost control interfaces, node management, memory, or administration.

## Internet / External Providers

External AI and cloud services are outside the household trust boundary. Outbound communication passes through controlled adapters and privacy policy.

## Minimum required flows

The preferred network policy is:

```text
DENY
then ALLOW only required flows
```

Exact VLAN IDs, addresses, ports, certificates, and firewall technology are deployment decisions and should not be hard-coded into domain architecture documentation.

## Remote administration

Normal operation must not require public port forwarding to HearthGhost Core, Node APIs, or Home Assistant administration.

Remote administration should use a separate authenticated private-access mechanism such as a VPN. Remote access is a management boundary, not a reason to expose the application directly to the Internet.

## Internal service egress

Not every server component requires Internet access.

Desired direction:

```text
Memory           -> no general Internet egress
Policy           -> no general Internet egress
Registry         -> no general Internet egress
LLM Adapter      -> approved provider egress only
Update component -> approved update sources only
```

Exact enforcement may evolve with the deployment platform, but unrestricted egress must not be the assumed default.
