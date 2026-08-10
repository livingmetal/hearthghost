# Privacy Model

## Goal

HearthGhost should minimize the amount of private household data that is captured, retained, or sent outside the home. Privacy is a system property, not a settings-page promise.

## Default media policy

```yaml
microphone:
  pre_wake_upload: denied
  continuous_stream: denied
  raw_audio_storage: denied

camera:
  default_access: denied
  continuous_stream: denied

cloud:
  text: allowed
  audio: denied
  image: denied
  video: denied
```

These are secure defaults. Future features may introduce explicit opt-in paths without weakening the default.

## Attention boundary

Audio that has not passed the Attention Gate is not conversation input.

It should not automatically flow to:

- STT
- LLM
- Memory
- cloud providers
- analytics
- long-term logs

This includes ordinary household conversation and television audio.

## Camera boundary

`camera.snapshot` and `camera.stream` are separate capabilities with different risk levels.

A camera request should have a reason and active authorization context. Node-local camera policy should be able to reject a request even when the server connection itself is authenticated.

The initial product does not require continuous household video streaming.

## Privacy Gateway

Data sent to an external AI provider must pass through an explicit privacy decision point.

```text
Core / Conversation
      |
Privacy Gateway
      |
Approved Adapter
      |
External Provider
```

Provider SDK convenience must not determine privacy policy.

## Data minimization

Do not retain data merely because storage is available.

Ephemeral by default:

- raw microphone audio
- temporary snapshots
- temporary perception frames
- wake-word buffers
- TV / unrelated ambient speech
- low-value sensor observations

Longer-lived data requires a defined purpose, such as:

- user-approved memory
- behavior preferences
- schedules and reminders
- device configuration
- security audit metadata

## Memory privacy

HearthGhost should not remember everything it hears.

Strong memory candidates include explicit user requests such as "이거 기억해". Other memories should pass a memory policy that considers usefulness, sensitivity, scope, and retention.

Conversations not addressed to Ghost are not memory candidates.

## Audit privacy

Audit logs should prove that a sensitive capability was used without storing the private content itself.

Preferred example:

```text
timestamp=...
action=camera.snapshot
node=livingroom-main
reason=user_vision_request
policy=allowed
result=success
```

Avoid placing image content, audio content, or entire private conversations into routine security logs.

## User visibility

The client UI should make privacy state easy to understand. Camera state, microphone/session state, and cloud-media policy should not be buried only in deep settings screens. Users should be able to determine whether the system is actively listening or viewing from the primary interface.
