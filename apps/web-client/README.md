# Web / Android client

This directory contains the shared TypeScript/Vite user interface and the
Capacitor Android shell selected by ADR-0005. The client is a presentation and
I/O endpoint, not the AI brain.

The tracked boundaries under `src/` preserve one application shell, one
semantic session model, and one `CharacterViewport` abstraction across
portrait and landscape modes. Renderer-specific code remains behind the
`CharacterRenderer` abstraction. The main screen stays character-first rather
than becoming a Home Assistant dashboard.

## Android security boundary

`src/node/android-platform.ts` exposes only semantic operations to the web
surface. The native plugin owns all security-sensitive operations:

- creates a P-256 Node identity in Android Keystore
- emits a PKCS#10 certificate signing request without exporting the private key
- validates and installs the administrator-issued public certificate chain
- opens the TLS 1.3, ALPN-authenticated Node Gateway connection
- parses bounded protocol frames and returns renderer-neutral events

The web surface receives an opaque credential reference, the public CSR and
fingerprint, and authenticated session metadata. It never receives private-key
material. The browser adapter fails clearly because a browser cannot provide
the reviewed native Keystore/mTLS boundary; tests use an explicitly selected
fake adapter.

Only Android's `INTERNET` permission is requested. The app does not request
camera, microphone, location, Bluetooth, nearby-device, or storage access.
Provider credentials, Home Assistant credentials, and Node private keys do not
belong in this package.

## Local web checks

```text
npm ci
npm run check
npm test
npm run build
```

## Reproducible Android build

The pinned rootless build is defined in `../../containers/android/Containerfile`.
It runs the web checks, Capacitor synchronization, Android unit tests, lint, and
debug APK assembly. See `../../containers/android/README.md` for the command and
artifact location.

HG-011's conversation parser accepts only the versioned text response,
renderer-neutral semantic events, and proposals explicitly marked
`pending_policy` and `not_executed`. Unknown fields, including provider-secret
fields and renderer-specific commands, fail closed.

See also:

- `../../docs/security/android-node-identity.md`
- `../../docs/architecture/character-presentation.md`
- `../../docs/product/mobile-ux.md`
- `../../docs/architecture/voice-attention.md`
- `../../docs/security/privacy-model.md`
