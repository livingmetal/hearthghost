# Node Architecture

## Principle

HearthGhost is one persistent AI identity with multiple possible physical bodies.

A phone, tablet, future robot, or sensor device is a **Node**, not a separate AI.

## Node model

A node should have at least:

```text
node_id
trust state
area or location
advertised capabilities
granted capabilities
connection state
```

Node identity, credentials, transport connections, authenticated Node sessions,
and conversation sessions are separate records. In particular, `node_id` is not
an IP address, hostname, room, user, or credential identifier. See
`../security/node-identity-and-replay.md`.

Example:

```yaml
node_id: livingroom-main
area: livingroom
capabilities:
  - display
  - microphone
  - speaker
  - camera.snapshot
  - touch
trust_state: trusted
```

Credential lifecycle is stored separately, so a credential can be revoked or
replaced without changing the logical Node identity. A trusted Node with a
revoked credential is still denied; trust does not reactivate credentials.

A future robot may expose:

```yaml
node_id: robot-dog-01
area: mobile
capabilities:
  - mobility.goto
  - camera.snapshot
  - microphone
  - speaker
  - follow_person
  - dock
  - battery.read
```

## Primary and secondary nodes

The first product experience assumes a primary living-room phone/tablet acting as HearthGhost's main face.

Future nodes may act as:

- secondary faces
- room microphones or speakers
- approved camera/sensor endpoints
- mobile robot bodies
- presence or environmental sensors

Primary status is a presentation preference, not ownership of identity or memory.

## Security posture

Each node must eventually have an independent, revocable identity. Do not reuse one long-lived credential on every household device.

Nodes should normally initiate outbound authenticated connections to the Node Gateway. They should not expose generic inbound camera/microphone HTTP servers merely for convenience.

A node must locally enforce security-sensitive capabilities such as camera access so that an authenticated but compromised Core is not automatically sufficient to activate them.

Authentication, trust, advertised capability, granted capability, current
Policy, and node-local authorization are independent checks. The Node Gateway's
successful authentication or request admission never waives a local camera or
microphone gate.

## Administration boundary

Node enrollment, trust changes, capability grants, and Node revocation require
an independently authenticated and action-authorized administrator. Enrollment
always creates an untrusted Node with no grants. Registry changes use optimistic
revisions and idempotency keys, and an actual change is committed atomically with
its privileged audit metadata. See `../security/node-administration.md`.

Administration success changes registry state only. It does not approve a
current action, create a Tool execution permission, or bypass a node-local gate.

## Capability routing

Requests should resolve by capability and context, not by hard-coded product names.

Example:

```text
User: "거실 사진 찍어줘"
required capability = camera.snapshot
required area = livingroom
       |
Device / Node Registry
       |
livingroom-main
```

Example:

```text
User: "침실에 가서 확인해줘"
required capabilities = mobility.goto + camera.snapshot
       |
Device / Node Registry
       |
robot-dog-01
```

## Future multi-node arbitration

When several nodes can hear the same wake word, the system will need a node-arbitration mechanism. Possible inputs include:

- near-field audio score
- wake confidence
- room presence
- node priority
- active conversation ownership
- user proximity
- future direction-of-arrival data

The MVP may start with one primary voice node. Multi-node arbitration is a later capability and must not complicate the first implementation prematurely.

## Personal phones versus dedicated nodes

Daily-use personal phones should not automatically become experimental always-on camera/microphone nodes. Dedicated spare phones/tablets are preferred for persistent HearthGhost sensing. Personal devices may later provide authenticated presence, notifications, or user identity signals with narrower permissions.
