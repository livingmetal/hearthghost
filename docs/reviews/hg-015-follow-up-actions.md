# HG-015 follow-up actions

Status: implementation complete enough for automated CI; physical-device validation remains required before household use.

## Automated issues discovered and addressed

- [x] Restore compatibility for callers importing `HEARTHGHOST_INSTRUCTIONS` after persona composition was introduced.
- [x] Keep `SECURITY_INSTRUCTIONS` as the immutable security-only prefix while making the legacy default constant represent the exact default composed prompt.
- [x] Keep Android `minSdkVersion = 29`; annotate the API-31-only on-device recognizer path rather than raising the application minimum SDK.
- [x] Install Android `platform-tools` explicitly in the pinned Android build image instead of relying on Gradle automatic installation.
- [x] Verify TypeScript/client tests in CI.
- [x] Verify Android unit tests, lint, and debug APK build in CI after the API-level fix.

## Physical Android validation required

- [ ] Install the debug APK on the target phone and complete the HG-014 Node enrollment flow.
- [ ] Confirm mobile-data access to `192.168.55.100:38443` over the private route while Samsung Wallet / vehicle applications remain outside the VPN path as configured.
- [ ] Confirm microphone permission is requested only after an explicit foreground touch.
- [ ] Confirm `Speak` cannot begin while Ghost is sleeping or while the app is backgrounded.
- [ ] Confirm Android reports an on-device recognizer for `ko-KR`; otherwise verify fail-closed text-only behavior.
- [ ] Capture network traffic during STT and verify no raw audio leaves the phone.
- [ ] Verify only the final transcript enters the existing `conversation.text` mTLS protocol.
- [ ] Verify local TTS uses an installed voice with `isNetworkConnectionRequired() == false` and falls back to text when no eligible voice exists.
- [ ] Verify attention expiry and app backgrounding cancel active STT/TTS promptly.
- [ ] Verify screen rotation, process recreation, call interruption, Bluetooth routing, and permission revocation do not bypass the native gates.

## Deferred design work

- [ ] Decide whether a future wake-word mode is acceptable. It must not reuse this touch-gated microphone path without a separate privacy review.
- [ ] Add device-level instrumentation tests for runtime permission and lifecycle behavior after the first physical validation pass.
- [ ] Do not add cloud STT/TTS fallback unless the default cloud-media policy and ADR-0008 are deliberately superseded by a reviewed decision.
