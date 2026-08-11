# Android Node identity and transport

## Security objective

The Android device is a HearthGhost Node. Its credential is not an application
secret and must not be exportable from the device. The TypeScript web surface
must not handle private-key material, TLS key managers, raw sockets, provider
credentials, or Home Assistant credentials.

## Identity lifecycle

1. The native plugin generates a P-256 signing key in `AndroidKeyStore`.
2. It verifies that the returned private key has no encoded representation.
3. It creates a PKCS#10 CSR containing the fixed development Node URI identity.
4. The UI displays only the CSR and its SHA-256 fingerprint for an explicit
   administrator enrollment step.
5. The administrator returns a public Node certificate and CA certificate.
6. Native code checks the key match, validity, CA constraints and signature,
   Node signature, digital-signature use, client-auth extended use, and exact
   URI subject alternative name.
7. Native code installs the certificate chain against the existing Keystore
   key. The private key never leaves Android Keystore.

There is no PKCS#12 import, embedded credential, generated certificate, or
private-key backup path.

## Native bridge boundary

The Capacitor bridge exposes narrow semantic methods for CSR creation,
certificate installation, connection, text conversation, and shutdown. It
returns an opaque credential reference rather than a key or keystore handle.
Operations run on a single-thread executor so the bridge admits only one
in-flight operation.

The browser implementation fails closed. It does not downgrade to plaintext or
emulate possession of a native credential. Unit tests explicitly inject the
fake platform adapter.

## Transport controls

- fixed development gateway: `192.168.55.100:38443`
- TLS 1.3 only
- ALPN `hearthghost-node/1`
- Android Keystore-backed client certificate authentication
- pinned installed development CA and HTTPS endpoint verification
- 5-second connection and 20-second socket timeouts
- maximum 16 KiB protocol frame
- monotonic request sequence numbers and bounded response parsing
- no automatic retry loop

Successful TLS proves possession of an enrolled credential; it does not itself
grant application trust or capabilities. After `session.open`, the native
client probes the text-conversation capability through the protocol and reports
the authenticated trust/grant result. Unknown response fields and unapproved
proposal states fail closed.

## Permissions and data

The source manifest requests only `android.permission.INTERNET`. Backup and
cleartext traffic are disabled. No camera, microphone, location, Bluetooth,
nearby-device, or storage permission is declared for this text-only slice.

OpenAI credentials remain server-side. `OPENAI_API_KEY` is neither read nor
logged by the Android application, passed through the web bridge, embedded in
the APK, supplied as a build argument, nor stored in Android Keystore.

## Remaining physical validation

HG-013 establishes and builds the Android security boundary. Physical-device
installation, CSR enrollment, and the first real text-only conversation are
performed as the next controlled step. No live provider call is required by
the normal test suite.
