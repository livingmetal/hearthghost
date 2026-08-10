# HearthGhost Roadmap

This roadmap describes capability milestones, not fixed release dates. Security foundations and contracts may move earlier than visible features when required.

## Foundation

Before feature milestones:

- threat model and trust boundaries
- repository/module skeleton
- policy model and schemas
- node identity direction
- versioned contracts
- audit/event conventions
- Privacy Gateway boundary

## v0.1 Conversational Ghost

Goal: prove that HearthGhost feels like a persistent conversational character rather than a voice-command appliance.

Target capabilities:

- primary mobile/tablet client
- portrait and landscape layouts
- renderer-neutral CharacterViewport
- basic character states
- text LLM adapter
- persona
- wake / attention foundation
- bounded conversation sessions
- STT/TTS integration
- ordinary conversation and humor
- touch-to-wake fallback

Success criterion:

> A user can naturally talk with Ghost for several minutes, while Ghost stays quiet when not addressed and the security model remains intact.

## v0.2 Secretary

Target capabilities:

- working and long-term memory foundation
- explicit "remember this" flow
- calendar integration
- reminders
- notes / todo tools
- behavior-preference updates through natural language
- initial user/household scope model

## v0.3 Smart Home

Target capabilities:

- Home Assistant adapter
- device/capability/tool registries
- Hue / SmartThings through the chosen home integration boundary
- room/area context
- low-risk home actions
- action risk metadata and confirmation policy
- secure device onboarding direction

## v0.4 Perception

Target capabilities:

- presence and motion context
- approved sensor observations
- event-driven camera snapshot flow
- local-first vision where practical
- explicit opt-in external vision path if ever enabled
- attention improvements using context

Continuous household camera streaming is not a milestone requirement.

## v0.5 Distributed Ghost

Target capabilities:

- multiple phone/tablet nodes
- per-node identity and revocation
- multi-room operation
- node capability routing
- multi-node wake arbitration
- secondary faces / room endpoints

## v0.6 Physical Extensions

Potential future capabilities:

- robot vacuum integration
- mobile robot / robot dog adapter
- mobile camera/perception body
- physical-action safety policies
- capability discovery and administrator approval

Physical autonomy must not advance faster than the authorization and safety model.

## Explicit non-goals for early releases

Do not make these prerequisites for initial usefulness:

- Kubernetes
- microservice decomposition
- a local large GPU LLM
- continuous video surveillance
- fully autonomous physical robots
- automatic control of every discovered IoT device
- perfect speaker recognition or gaze tracking

The project should earn complexity through demonstrated needs.
