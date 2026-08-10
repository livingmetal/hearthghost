# Voice and Attention Architecture

## Problem

A household AI must distinguish speech addressed to the character from television audio, conversations between household members, and unrelated ambient speech.

The first question is not "what intent is this?" but:

> Was this utterance addressed to HearthGhost?

## Default state

The default state is `SLEEPING`.

Before a trusted attention event, raw household speech should remain local to the node as far as practical and must not automatically enter STT, LLM, Memory, or cloud processing.

## Initial attention flow

```text
Microphone
  |
Local VAD
  |
Local Wake Word
  |
Attention Gate
  |---- rejected -> discard
  |
Conversation Session
  |
STT / Conversation
```

The preferred initial activation methods are:

- character name / wake word
- touch-to-wake fallback

Near-field speech should be preferred where practical to reduce television and room-audio false activation.

## Conversation session

After an explicit activation, HearthGhost should allow bounded wake-word-free follow-up conversation.

```text
SLEEPING
 -> LISTENING
 -> THINKING
 -> SPEAKING
 -> ENGAGED
      |-- follow-up -> LISTENING
      |-- timeout   -> SLEEPING
```

Conversation timeout is a Behavior Preference and must not be scattered as a hard-coded constant.

A user should be able to say things such as:

- "조금 더 기다려."
- "대화가 끝난 뒤 빨리 쉬는 상태로 돌아가."

The LLM may interpret such requests into typed preference-update proposals; the Policy Manager validates and persists them.

## Future attention signals

The architecture should allow later use of:

- speaker verification
- person proximity
- face direction or gaze
- sound direction
- device proximity
- active-session ownership
- node arbitration

None of these advanced mechanisms are required for the first conversational MVP.

## TV and household conversation

Wake word alone is not assumed to be perfect. Later attention scoring may combine multiple signals, but HearthGhost should remain conservative: if it is unclear whether speech is addressed to Ghost, remaining silent is preferable to interrupting household conversation.

## Echo and self-hearing

When TTS and microphone input operate simultaneously, the voice architecture should be prepared for acoustic echo cancellation or an equivalent self-audio suppression mechanism. HearthGhost must not repeatedly transcribe and respond to its own TTS output.

The exact AEC implementation is intentionally deferred.

## Raw audio retention

Raw audio is ephemeral by default. Routine operation should not require permanent storage of household microphone data. Audit records should describe session metadata rather than archive private audio.
