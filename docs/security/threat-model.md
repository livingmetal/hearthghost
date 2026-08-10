# Threat Model

## Security objective

The highest-priority security goal is to prevent an attacker from turning HearthGhost into a household surveillance or unsafe physical-control platform.

A successful compromise of one component must not automatically provide unrestricted access to cameras, microphones, private memory, trusted personal networks, Home Assistant administration, or physical actuators.

## Protected assets

High-value assets include:

- live household camera access
- live household microphone access
- conversation history and long-term memory
- personal schedules, reminders, and preferences
- device credentials and certificates
- Home Assistant credentials
- LLM/API credentials
- trusted user identities
- physical-control capabilities such as locks, robots, heaters, doors, and future actuators
- the trusted household network

## Threat actors and compromise assumptions

Assume possible compromise of:

- HearthGhost Core through an application vulnerability
- an Android node through OS/app compromise or physical theft
- an IoT device with weak vendor security
- Home Assistant or one of its integrations
- an external AI provider account or API credential
- a future robot or vendor adapter
- the local Wi-Fi/LAN by an unauthorized device
- untrusted web/document/camera content through prompt injection

## Major abuse cases

### 1. Core takeover -> camera surveillance

Attacker controls HearthGhost Core and sends camera requests to every node.

Required defenses:

- node-local camera authorization gate
- session/context-bound camera permission
- continuous streaming disabled by default
- per-node identity and capability ACLs
- security audit event for camera access

Desired result: Core compromise alone is insufficient for unrestricted camera access.

### 2. Node theft or compromise -> lateral movement

Attacker steals or compromises one spare Android node.

Required defenses:

- per-node credential
- revocation capability
- no shared universal node secret
- network segmentation
- node cannot freely reach trusted personal devices
- permissions limited to that node's capabilities

Desired result: one node is disposable without rebuilding trust for every node.

### 3. Malicious IoT device -> AI/Core access

A compromised light, plug, camera, or other IoT product attempts to scan or attack HearthGhost or personal devices.

Required defenses:

- IoT network isolation
- deny-by-default firewall policy
- adapter-mediated access
- no assumption that home LAN membership equals trust

### 4. Prompt injection -> physical action

A web page, document, OCR result, email, camera-visible text, or robot sensor payload contains instructions telling the LLM to expose secrets or operate devices.

Required defenses:

- external content classified as untrusted data
- LLM cannot directly execute devices
- every tool proposal passes Policy Engine
- critical actions require independent authorization/confirmation
- secrets are not generally available to conversation reasoning

### 5. Cloud/provider compromise -> household media exposure

An external provider or API key is compromised.

Required defenses:

- text-only cloud access by default
- image/audio/video cloud transfer denied by default
- Privacy Gateway
- scoped provider credentials
- no routine raw household media retention in provider-facing components

### 6. Credential leak from repository/logs

Developer accidentally commits or logs API keys, HA tokens, private keys, or household secrets.

Required defenses:

- secrets prohibited in Git
- fake `.env.example` values only
- log redaction
- narrowly scoped secrets per service
- secret scanning may be added later

### 7. Unsafe robot or physical action

LLM misunderstands a request, malicious input manipulates it, or a component is compromised and proposes a dangerous physical action.

Required defenses:

- risk metadata on tools
- Policy Engine independent of LLM reasoning
- required context and user role
- confirmation for critical actions
- device safety state validation
- fail closed when policy or device state is unknown

## Availability versus privacy

Privacy and physical safety outrank availability. If a policy service, identity check, or security-sensitive state cannot be verified, sensitive actions should be denied rather than executed optimistically.

## Residual risk

No software-only architecture can guarantee privacy if the Android OS, camera firmware, microphone subsystem, or physical device hardware itself is malicious. HearthGhost reduces system-level blast radius but does not claim to solve malicious hardware or fully compromised device operating systems.

Security assumptions and residual risk must remain explicit rather than being hidden behind claims of absolute security.
