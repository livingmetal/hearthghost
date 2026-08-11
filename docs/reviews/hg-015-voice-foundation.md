# HG-015 Voice foundation review

## Result

Software foundation implemented on top of the HG-013 Android Node and the stacked attention/persona work. Physical validation is required before this milestone is accepted for household use.

## Implemented boundary

- Android native `VoiceInputPlugin` requests `RECORD_AUDIO` only at runtime.
- microphone start requires foreground window focus and a recent Activity user interaction.
- Android voice input requires API 31+ and `isOnDeviceRecognitionAvailable()`.
- only `createOnDeviceSpeechRecognizer()` is permitted; there is no generic recognizer fallback.
- raw audio buffers and partial transcripts are not bridged to JavaScript.
- final transcript is bounded and marked `on_device_stt`.
- client voice controller requires active touch attention before forwarding the transcript into the existing text conversation path.
- backgrounding or attention timeout cancels recognition.
- Android `VoiceOutputPlugin` chooses only installed TTS voices that do not require a network connection.
- voice-originated replies may use embedded TTS; typed replies remain text-only.
- cloud audio remains denied and Core receives text only.

## Static verification added

- Android manifest permission allowlist is now exactly `INTERNET` plus `RECORD_AUDIO`.
- source tests reject generic `createSpeechRecognizer()` and `EXTRA_PREFER_OFFLINE` fallback.
- source tests require the recent-touch and foreground checks.
- source tests verify raw audio and partial callbacks do not notify the WebView.
- source tests reject network/provider clients inside voice plugins.
- TTS tests require `isNetworkConnectionRequired()` filtering and reject network synthesis fallback.
- client tests reject voice transcripts without active attention, after timeout, from a non-local source, or with malformed confidence.

## Physical validation still required

On the designated Android phone:

1. install the newly built debug APK;
2. complete HG-014 Node enrollment/mTLS first;
3. confirm microphone permission is requested only after an explicit tap;
4. confirm Android reports on-device speech recognition availability;
5. test Korean speech while mobile data and Wi-Fi are separately disabled where practical to demonstrate recognition does not depend on network reachability;
6. confirm late recognition results after attention expiry are rejected;
7. confirm leaving the app cancels microphone recognition;
8. inspect runtime network traffic during voice capture and verify only transcript/Core traffic follows recognition, not raw audio provider traffic;
9. verify a non-network Korean TTS voice is selected or text fallback is used;
10. re-run Android unit/lint/build and the full Python/client suites.

## Explicitly deferred

- wake-word detection
- continuous VAD/listening
- speaker identification
- cloud STT
- raw PCM streaming to Core
- multi-node wake arbitration
- proactive speech
