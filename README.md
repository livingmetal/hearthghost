# HearthGhost

> A security-first, character-based household AI companion and personal secretary.

HearthGhost is an open-source home AI platform designed to exist as a persistent character in the household rather than as a simple voice-command interface.

Its primary interface is expected to be an Android phone or tablet acting as the AI's face, ears, eyes, and voice. The central HearthGhost server provides conversation orchestration, memory, policy enforcement, tool execution, device management, and integration with external AI services.

The project is designed around one principle above all others:

> **Privacy and physical safety take priority over convenience, automation, and character experience.**

---

## 1. Project Goals

HearthGhost should eventually support:

- natural everyday conversation
- jokes and character-driven interaction
- persistent persona and configurable behavior
- calendar, reminders, notes, and personal-assistant functions
- Home Assistant-based smart-home control
- SmartThings, Philips Hue, Matter, MQTT, and future IoT integrations
- context-aware interaction using room, presence, and sensor information
- user-requested camera and vision capabilities
- multiple Android phones and tablets as distributed household nodes
- future robots such as robot vacuums or robot dogs
- extensible tools and device capabilities without redesigning the AI core

HearthGhost is **not** intended to become a cloud-connected surveillance system or an unrestricted autonomous home controller.

---

## 2. Security-First Threat Model

The system must be designed under the assumption that any individual component may eventually be compromised.

This includes:

- the HearthGhost Core
- an Android node
- an IoT device
- Home Assistant
- an external LLM provider
- a future robot or third-party adapter

A compromise of one component must not automatically provide an attacker with unrestricted access to:

- household cameras
- continuous microphone streams
- private conversations
- long-term memory
- Home Assistant administrator privileges
- door locks or other critical physical devices
- other HearthGhost nodes
- trusted personal devices or networks

Security must therefore rely on multiple independent trust boundaries rather than a single trusted server.

---

## 3. Non-Negotiable Security Rules

The following are **Hard Policies** and must not be bypassable by an LLM or ordinary voice command.

| Capability | Default policy |
| --- | --- |
| Continuous camera access | DENY |
| Continuous microphone streaming | DENY |
| Uploading pre-wake audio | DENY |
| Storing pre-wake conversation | DENY |
| Automatic cloud upload of household images | DENY |
| Automatic cloud upload of raw household audio | DENY |
| Inbound network services on household nodes | DENY by default |
| Direct Internet exposure of HearthGhost Core | DENY |
| Direct LLM access to devices | DENY |
| Direct LLM access to Home Assistant | DENY |
| LLM modification of Hard Policies | DENY |
| Automatic control of newly discovered devices | DENY |
| Unconfirmed critical physical actions | DENY |

The secure failure mode is **fail closed**.

If identity, authorization, policy state, or device state cannot be verified, the requested sensitive action must not execute.

---

## 4. High-Level Architecture

```text
                         Internet
                            |
                    Controlled Egress
                            |
                      Privacy Gateway
                            |
                       LLM Adapter
                            |
                            v
+-------------------------------------------------------+
|                HearthGhost Core Server               |
|                                                       |
|  Conversation   Orchestrator   Memory                 |
|  Policy Engine  Tool Registry  Device Registry        |
|  Node Gateway   Privacy        Audit                  |
+------------------------+------------------------------+
                         |
          +--------------+---------------+
          |                              |
          v                              v
   Sensor / Node Zone                IoT Zone
          |                              |
   Android phones/tablets            Home Assistant
   camera / mic / speaker            Hue / SmartThings
   display / touch                    future devices
          |
          v
   Local security gates
```

The initial runtime target is a single Linux home server:

- WTR PRO
- AMD Ryzen 7 5825U
- GPU must not be assumed

The initial implementation should prefer a **modular monolith** and simple container/process isolation over Kubernetes or premature microservices.

---

## 5. One AI, Multiple Bodies

HearthGhost represents one persistent AI identity that may appear through multiple physical nodes.

A node may provide capabilities such as:

```text
display
speaker
microphone
camera
touch
motion
presence
```

Examples:

```text
Living-room tablet
= primary face + ears + eyes + voice

Entrance phone
= camera / sensor node

Future robot dog
= mobile body + camera + microphone + speaker
```

The AI identity and memory belong to HearthGhost, not to any individual device.

Replacing a tablet must not create a new Ghost.

---

## 6. Attention Before Intelligence

HearthGhost must not treat every sound in the room as a command or conversation.

Normal state:

```text
SLEEPING
```

A conversation normally begins through an explicit attention signal such as:

- character wake word
- touch interaction
- another explicitly trusted activation mechanism

Near-field speech should be preferred when practical so that television audio and unrelated household conversation are less likely to activate the system.

Before activation, raw household speech should remain local to the node and should not be forwarded to STT, LLM, Memory, or cloud services.

A simplified flow is:

```text
Microphone
    |
 Local VAD
    |
Local Wake Detection
    |
 Attention Gate
    |
    +-- not addressed to Ghost --> discard
    |
    v
Conversation Session
    |
   STT
    |
HearthGhost Core
```

---

## 7. Conversation Sessions

After explicit activation, HearthGhost should support a limited period of natural follow-up conversation without requiring the wake word before every sentence.

```text
SLEEPING
   |
   v
LISTENING
   |
   v
THINKING
   |
   v
SPEAKING
   |
   v
ENGAGED
   | \
   |  +--> timeout --> SLEEPING
   |
   +---- follow-up --> LISTENING
```

The session timeout must be configurable as a behavior preference.

The system should later be able to combine signals such as:

- wake word
- near-field audio
- speaker identity
- person proximity
- face direction or gaze
- touch
- existing conversation context

These signals improve attention detection, but advanced speaker or vision recognition must not be required for the first MVP.

---

## 8. Conversation Is the Primary Interface

HearthGhost must not be designed as a command parser with a chat feature attached.

Conversation is the primary interaction model.

A user statement may represent:

```text
CHAT
KNOWLEDGE REQUEST
SECRETARY REQUEST
ACTION REQUEST
OBSERVATION
```

Examples:

```text
"오늘 힘들었다."
-> conversation

"내일 일정 알려줘."
-> secretary tool may be used

"거실 불 꺼줘."
-> explicit device action

"좀 어둡네."
-> observation, not automatically a command
```

Ambiguous observations should not automatically become physical actions.

---

## 9. LLM Trust Model

The LLM is a reasoning and interpretation component, not a trusted execution authority.

The LLM may:

```text
interpret
reason
plan
propose tools
produce conversation
```

The LLM must not directly:

```text
access cameras
access raw microphones
control Home Assistant
control robots
modify security policy
read arbitrary secrets
perform unrestricted OS commands
administer databases
```

External actions must follow this path:

```text
LLM
 |
Tool Proposal
 |
Policy Engine
 |
Authorization / Risk Check
 |
Executor
 |
Adapter
 |
Device
```

---

## 10. Policy Model

Policies are divided into two major classes.

### Hard Policy

Security, privacy, authorization, and critical-action controls.

Examples:

- camera access restrictions
- cloud-media restrictions
- critical physical-action confirmation
- device onboarding permissions
- administrator permissions

These cannot be modified through ordinary LLM conversation.

### Behavior Preferences

User-adjustable interaction characteristics.

Examples:

```yaml
character:
  humor: moderate
  verbosity: normal
  formality: casual
  initiative: low

conversation:
  followup_timeout_sec: 20

proactive:
  frequency: low
```

Users should be able to modify these naturally:

```text
"농담을 좀 더 많이 해."
"답을 좀 짧게 해."
"말 끝난 다음에 조금 더 기다려."
"별일 아니면 먼저 말 걸지 마."
```

The LLM interprets the request and proposes a typed policy update. A Policy Manager validates and stores it.

The LLM must never edit policy files directly.

---

## 11. Camera and Microphone Privacy

### Microphone

Before wake:

```text
raw audio -> local processing only -> discard
```

After a trusted attention event:

```text
audio -> authenticated encrypted session -> HearthGhost STT
```

Raw audio should not be persistently stored by default.

### Camera

Camera access is denied by default.

Snapshot and continuous streaming are separate capabilities:

```text
camera.snapshot
camera.stream
```

Continuous streaming has a higher risk level and is not required for the initial version.

A node must maintain its own local Camera Gate. This is deliberate: even if HearthGhost Core is compromised, the server should not automatically gain unrestricted camera access.

A legitimate request may look like:

```text
User: "이게 뭐야?"
        |
Active Conversation
        +
Explicit Vision Intent
        |
Local Camera Gate
        |
Snapshot
```

---

## 12. Cloud Privacy Boundary

All outbound AI-provider traffic must pass through an explicit privacy boundary.

Default policy:

```yaml
cloud:
  text: allow
  audio: deny
  image: deny
  video: deny
```

This means cloud LLM text conversation may be supported while raw household media remains local by default.

Cloud Vision, cloud STT, or similar features may be added later only as explicit, reviewable opt-in capabilities.

---

## 13. Device, Capability, and Tool Registries

HearthGhost must not encode every product directly into the AI core.

Devices expose capabilities.

Example:

```text
robot-dog-01

capabilities:
  mobility.goto
  camera.snapshot
  follow_person
  speak
  dock
  battery.read
```

The system distinguishes:

```text
Device Registry
    what exists?

Capability Registry
    what can each device do?

Tool Registry
    which capabilities are exposed to the AI?

Policy Engine
    may this action happen now?
```

This allows future IoT devices, robots, and sensors to be added without redesigning the conversation core.

---

## 14. Secure Device Onboarding

Device discovery does not equal trust.

```text
Device discovered
      |
   UNTRUSTED
      |
Capability inspection
      |
Administrator approval
      |
Permission assignment
      |
    TRUSTED
```

A newly discovered device must not automatically receive AI control permissions.

Each HearthGhost node should eventually have its own identity and revocable credential.

Compromise of one node must not automatically authenticate another node.

---

## 15. Home Assistant Integration

Home Assistant is a tool backend, not the HearthGhost brain.

Required direction:

```text
Conversation
    |
   LLM
    |
Tool Proposal
    |
Policy Engine
    |
Home Adapter
    |
Home Assistant
```

The LLM must not have direct Home Assistant credentials.

HearthGhost integrations should use the least privilege realistically available and should not rely on an administrator credential for routine device control.

---

## 16. Future Robots and Physical Devices

Physical robots carry more risk than ordinary lights or media devices.

Every tool must be able to declare metadata such as:

```yaml
name: robot.goto
risk_level: medium
required_context: explicit_user_request
confirmation_policy: explicit
```

Higher-risk examples such as locks, security systems, external doors, financial actions, or potentially hazardous actuators require stronger confirmation and authorization.

An LLM-generated plan never overrides physical safety policy.

---

## 17. Memory Policy

HearthGhost should support long-term memory, but it must not remember everything it hears.

Potential memory classes:

```text
Working Memory
Episodic Memory
Semantic Memory
User Preference
System Configuration
```

The following must not automatically become long-term memories:

- pre-attention audio
- television audio
- conversations not addressed to Ghost
- temporary camera frames
- temporary sensor observations

Explicit requests such as `"이거 기억해"` should be treated as strong memory candidates, subject to privacy and authorization policy.

---

## 18. Proactive Behavior

HearthGhost may eventually speak or act proactively, but the default must be conservative.

```yaml
proactive:
  interrupt_household_conversation: false
  interrupt_tv: false
  physical_action_without_request: restricted
  frequency: low
```

A useful companion is not one that comments on everything happening in the room.

---

## 19. Network and Service Principles

The deployment should eventually support logical separation between:

```text
Trusted User Zone
AI Core Zone
Sensor / Node Zone
IoT Zone
Guest / Untrusted Zone
```

Default network policy is:

```text
DENY
then explicitly ALLOW required flows
```

Household nodes should normally initiate outbound authenticated connections to the Node Gateway rather than expose inbound camera or microphone services.

HearthGhost Core and Home Assistant administration must not be directly port-forwarded to the public Internet.

Remote administration should occur through a separate authenticated private-access mechanism such as a VPN.

---

## 20. Secrets, Audit, and Revocation

Secrets must never be committed to the repository.

This includes:

- API keys
- certificates and private keys
- Home Assistant tokens
- device credentials
- database credentials

Sensitive operations should produce metadata-oriented audit events without unnecessarily logging private content.

Examples:

```text
node registration
failed authentication
policy change
tool execution
tool rejection
camera access
microphone session
cloud media transfer
critical physical action
administrator action
```

Individual node or device credentials must be revocable without rebuilding the entire system.

---

## 21. Development Architecture

HearthGhost starts as a **monorepo** and **modular monolith**.

Expected logical modules include:

```text
Conversation
Orchestrator
Policy
Memory
Voice
Character
Perception
Registry
Tools
Adapters
Node Gateway
Privacy Gateway
Audit
```

External implementations belong behind adapters:

```text
LLM providers
STT engines
TTS engines
Home Assistant
Vision providers
Robot vendors
```

Do not introduce Kubernetes, Kafka, distributed databases, or microservices simply because they may be useful someday.

Security boundaries should first be implemented using clear interfaces, least privilege, process/container isolation, network policy, and explicit authentication.

---

## 22. Development Rules

Every implementation task must respect these rules:

1. Security boundaries take priority over feature convenience.
2. New external network access requires justification.
3. New tools require risk classification.
4. New device adapters require explicit permissions.
5. Camera and microphone features require privacy review.
6. Hard Policy bypasses are prohibited.
7. Provider-specific implementations belong behind adapters.
8. Secrets must never be committed.
9. Security-sensitive behavior requires tests.
10. Architecture and security-boundary changes must be documented.
11. Prefer simple designs over premature distributed architecture.
12. When uncertain about a sensitive action, fail closed.

---

## 23. Initial Development Priorities

Before implementing advanced AI features, establish the project's trust boundaries and contracts.

Suggested order:

```text
Security architecture and threat model
        |
Repository / module skeleton
        |
Contracts and policy schemas
        |
Node identity and authenticated transport
        |
Attention + conversation session
        |
Text conversation
        |
Character presentation
        |
Voice STT/TTS
        |
Memory
        |
Home Assistant tools
        |
Perception
        |
Vision
        |
Distributed nodes
        |
Robots / additional physical devices
```

The first useful milestone should prove that HearthGhost can hold a natural conversation while preserving the security model, not merely demonstrate that it can turn a light on and off.

---

## 24. Security Priority Order

When requirements conflict, use this order:

```text
1. Physical Safety
2. Privacy
3. Authentication and Authorization
4. Data Protection
5. System Integrity
6. Availability
7. Convenience
8. Character Experience
```

HearthGhost should be useful, personable, and extensible, but never by quietly weakening the privacy of the people who live with it.

---

## Development Validation

The preferred reproducible validation path uses the repository test image:

```text
docker compose build --pull test
docker compose run --rm test
```

The image currently contains only Python 3.13 and the repository. It installs no
project dependencies and does not select Python as the final Assistant runtime.
The test service runs as an unprivileged user with no network, no Linux
capabilities, a read-only root filesystem, no ports, no host devices, no Docker
socket, and no persistent volumes.

Rootless Podman can run the same image when a Compose provider is unavailable:

```text
podman build --pull=always --target test -t hearthghost-test:local .
podman run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --cap-drop=all --security-opt=no-new-privileges hearthghost-test:local
```

Host-side standard-library validation remains available:

```text
python -m unittest discover -s tests -p "test_*.py"
```

The minimal, internal-only Core runtime can be started without publishing a
host port:

```text
docker compose --profile runtime up --build -d core
docker compose --profile runtime exec core \
  python -m apps.assistant.src.runtime.healthcheck
docker compose --profile runtime down
```

---

## Status

HearthGhost has an implementation foundation, versioned contracts, the core
Node security boundary, a privileged Node administration boundary, and a TLS
1.3 mutual-authentication adapter. A minimal containerized Core keeps deny-only
defaults and loopback health/status. The separate HG-012 development runtime
adds a narrowly published rootless mTLS Node listener, restrictive file-backed
development registry/credential state, explicit local administration, and a
development PKI whose authority remains outside the container and repository.
A test-only Mock Node proves the framed lifecycle. There is still no production
deployment, physical device integration, administrator identity provider,
production PKI, database, or Policy allow path.

The next physical slice packages the reviewed web client in Android, keeps the
Node private key non-exportable in Android Keystore, and connects through the
narrow native mTLS bridge. It must not bypass Policy, Privacy Gateway,
node-local media gates, or adapter isolation.
