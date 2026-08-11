# HG-013 Android Node review

## Result

Accepted for debug APK handoff pending physical-device installation. HG-014
does not begin until a designated spare Android phone is connected to WTR PRO
with USB debugging explicitly authorized.

## Source baseline

- source branch: `codex/hg-012-development-runtime`
- source commit: `408eed24da6bbfd943b8f8110cb6de8cd034202a`
- pre-change tests: 148 Python and 18 client tests passed

## Implemented boundary

- Capacitor Android 8.5.0 wraps the shared TypeScript/Vite client.
- Android API 29 is the minimum; compile/target API is 36.
- a narrow Capacitor plugin owns Keystore identity, certificate-chain
  installation, TLS, protocol framing, and response validation
- Android Keystore generates a non-exportable P-256 identity and signs a
  PKCS#10 CSR without exposing the private key
- certificate installation validates the exact Node URI identity and intended
  client-auth usage before replacing the public chain on the Keystore entry
- native mTLS is fixed to the development Gateway, TLS 1.3, and
  `hearthghost-node/1` ALPN
- the bridge is single-flight, bounded, timeout-controlled, serially replay
  protected, and has no automatic retry loop
- TLS success is not treated as trust or capability grant
- the Android source manifest requests only `INTERNET`; backup and cleartext
  traffic are disabled
- provider credentials remain exclusively server-side

## Reproducible build

- pinned Node and Temurin base image digests
- pinned Google command-line tools archive and SHA-256
- pinned Android platforms/build tools and Gradle wrapper
- non-root final build user
- network-disabled execution after image construction
- web type checks, client tests, Vite build, Android unit tests, lint, and APK
  assembly run in the builder

## Verification evidence

- Python suite: 152 tests passed in the network-disabled rootless test image
- client suite: 18 tests passed in the Android builder
- Android unit/lint/assembly: Gradle completed 140 tasks successfully
- debug APK SHA-256:
  `83a50ea95d02367984c048e4cd2bbaf325dc20f2a646e1fb409b9fd8f6398e82`
- APK signature: APK Signature Scheme v2 verified with one Android debug signer;
  the debug signing identity is separate from the Node identity
- packaged permissions: `INTERNET` plus AndroidX's package-scoped
  non-exported dynamic-receiver permission; no sensitive permission
- physical device: not detected on WTR PRO at review time
- secret and generated-artifact scan: no private-key/API-key literal or ignored
  credential/build artifact is tracked in the commit tree

## Deferred to physical-device handoff / HG-014

- install debug APK on the designated spare phone
- generate the device-held CSR and perform administrator-approved enrollment
- prove the private key remains non-exportable on the target device
- establish native mTLS and observe trust/capability state
- perform the first real Android text-only end-to-end conversation through the
  Privacy Gateway using the server-side Luna provider credential
- stop after that first successful real text-only end-to-end result
