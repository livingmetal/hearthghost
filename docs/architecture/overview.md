# Architecture Overview

## Purpose

HearthGhost is a security-first, persistent household AI companion and personal secretary. It is not a smart-home command parser with a chat feature attached. Conversation is the primary interface; tools, memory, environment control, and perception extend that conversation.

## Initial deployment target

```text
Single Linux home server
WTR PRO
AMD Ryzen 7 5825U
GPU not assumed
```

The initial implementation should be a monorepo and modular monolith. Separate processes or containers are justified when they create a meaningful security, lifecycle, or runtime boundary. Kubernetes, Kafka, service meshes, and distributed databases are not initial requirements.

## Core logical modules

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

### Conversation
Maintains dialogue context, persona-facing interaction, response flow, and natural conversation semantics.

### Orchestrator
Coordinates reasoning, tool proposals, memory access, response planning, and external adapters. It must not become a universal god object that bypasses module boundaries.

### Policy
Evaluates behavior preferences, authorization, risk, hard security policy, and action confirmation requirements. Policy decisions are not delegated to the LLM prompt alone.

### Memory
Maintains working, episodic, semantic, preference, and configuration memory according to explicit privacy and retention rules.

### Voice
Owns VAD, wake handling, attention integration, STT/TTS abstraction, conversation audio sessions, and future echo-control integration.

### Character
Represents semantic character state and presentation contracts. It must remain independent from any specific 2D or 3D renderer.

### Perception
Turns approved sensor, presence, and vision observations into structured context. Continuous household surveillance is not an architectural goal.

### Registry
Maintains devices, node identities, capabilities, tools, areas, and related metadata.

### Tools
Defines actions the AI may propose. Tool execution is always mediated by policy and authorization.

### Adapters
Contain provider- or product-specific implementations such as LLM providers, STT/TTS engines, Home Assistant, vision providers, robot vendors, and future smart-home protocols.

### Node Gateway
Handles authenticated communication with household phone/tablet/robot nodes.

### Privacy Gateway
Controls data that may leave the local trust boundary for external AI or cloud services.

### Audit
Records security-relevant metadata without turning logs into a second surveillance archive.

## Dependency direction

Core domain logic depends on ports/interfaces, not provider implementations.

```text
User / Node
   |
Attention + Conversation
   |
Orchestrator
   |
+-- Memory
+-- Policy
+-- Registry
+-- Tool Planner
        |
        v
     Policy Check
        |
     Executor
        |
     Adapter
        |
External service / device
```

The LLM may interpret, reason, plan, converse, and propose. It is not an execution authority.

## One AI, multiple bodies

The HearthGhost identity does not live in one tablet. A living-room tablet may be the primary face, while future phones, tablets, cameras, or robots can become additional nodes that provide capabilities.

Replacing a node must not create a new Ghost or split identity and memory.

## Local and cloud responsibility

The architecture must allow provider substitution. Cloud LLMs may be used initially, while local models may be added later through adapters without redesigning the core.

The target server is suitable for orchestration, Home Assistant, databases, policy, node management, and selected lightweight local AI workloads. The system must not assume a local GPU or require a large local LLM.

## Security as architecture

Assume any single component may be compromised. Sensitive actions should cross more than one independent control boundary when practical. In particular, a compromised Core must not automatically grant unrestricted camera or microphone access on nodes.
