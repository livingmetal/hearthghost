# ADR-0008: On-device voice MVP

## Status

Accepted for the Android v0.1 voice foundation; physical-device validation remains pending.

## Context

HearthGhost treats microphone data as a sensitive local capability. Pre-attention household audio must not be forwarded to Core, STT providers, Memory, or cloud services. The default cloud privacy policy denies audio.

Android's ordinary `SpeechRecognizer.createSpeechRecognizer()` may use a recognizer implementation that streams audio to remote servers. `RecognizerIntent.EXTRA_PREFER_OFFLINE` is only a preference and may be ignored by a recognizer implementation. Android API 31 introduced a distinct `createOnDeviceSpeechRecognizer()` factory plus `isOnDeviceRecognitionAvailable()`.

HearthGhost's Android minimum SDK remains 29, so voice must degrade safely on devices that cannot prove an on-device recognizer.

TTS has a similar privacy concern. Android TTS engines expose `Voice.isNetworkConnectionRequired()`. The framework recommends selecting a Voice that does not require network connectivity for embedded synthesis.

## Decision

### Speech input

The first voice MVP uses Android on-device speech recognition only.

```text
physical user touch
      |
      v
native recent-touch gate
      |
      v
RECORD_AUDIO runtime permission
      |
      v
API >= 31 + on-device recognizer available
      |
      v
createOnDeviceSpeechRecognizer()
      |
      v
final transcript only
      |
      v
client AttentionController
      |
      v
existing conversation.text mTLS path
```

The implementation must not fall back to `createSpeechRecognizer()` or rely on `EXTRA_PREFER_OFFLINE`.

Raw `onBufferReceived()` microphone bytes and partial recognition results are ignored and never bridged to JavaScript. Only the final bounded transcript may cross the native/WebView boundary.

The native plugin independently requires:

- `RECORD_AUDIO` runtime permission;
- a foreground Activity with window focus;
- a recent physical user interaction;
- Android 12 / API 31 or newer;
- `SpeechRecognizer.isOnDeviceRecognitionAvailable()`;
- a single active recognition session.

A JavaScript call alone is therefore insufficient to start microphone capture from a sleeping/background state.

### Speech output

Replies originating from voice input may be spoken using Android TTS only when an installed voice:

- matches the requested language;
- reports `isNetworkConnectionRequired() == false`;
- does not report `KEY_FEATURE_NOT_INSTALLED`.

If no such voice is available, HearthGhost remains text-only. It does not trigger a voice download and does not fall back to a network-required voice.

Typed conversation replies remain text-only in this milestone. Automatic TTS is limited to a reply following explicit voice input.

### Cloud boundary

No raw voice media enters `PrivacyGateway` in this MVP. Core receives the same bounded text command used by typed conversation. The existing default remains:

```yaml
cloud:
  text: allow
  audio: deny
  image: deny
  video: deny
```

## Consequences

### Positive

- raw household microphone data remains on the Android node;
- ordinary Android speech recognizers that may use remote services are excluded;
- unsupported devices fail closed to text conversation;
- existing mTLS and conversation protocol need no audio framing or larger message limits;
- voice output can remain local when an embedded TTS voice exists;
- Core and LLM providers receive text only.

### Negative

- Android 10/11 devices cannot use the voice MVP even though the app itself can run there;
- some Android 12+ devices may have no on-device recognition service or installed language model;
- the physical-device test must verify the target phone actually exposes Korean on-device recognition and an embedded Korean TTS voice;
- wake-word recognition remains separate future work; this milestone uses explicit touch attention.

## Rejected alternatives

### Ordinary Android SpeechRecognizer with offline preference

Rejected because the Android documentation states speech recognition implementations may stream audio to remote servers and the offline preference may have no effect.

### Cloud STT

Rejected for the default v0.1 path because cloud audio is denied by Hard Policy direction.

### Send raw PCM to Core for future local STT

Deferred. It would require a new bounded streaming transport, microphone-session capability, additional replay/backpressure semantics, and careful retention controls. It is unnecessary while the target Android node can perform on-device STT.

### Network-required Android TTS voice

Rejected for automatic voice output. Text fallback is preferred to an unreviewed network synthesis path.
