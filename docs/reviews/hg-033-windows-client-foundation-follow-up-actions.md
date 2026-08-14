# HG-033 Windows client foundation follow-up actions

## Goal

Make Windows a first-class HearthGhost development client alongside Android so the shared UI, VRM character behavior and real Core conversation can be inspected quickly from the developer's Windows environment.

## Implemented

- Added a WPF + WebView2 Windows shell on .NET 10.
- Added a strict WebView2 request/response bridge with bounded request count and timeout.
- Added `WindowsNodePlatform` implementing the existing `NodePlatformPort` and `TextConversationTransportPort` contracts.
- Added a Windows-native `SslStream` transport using TLS 1.3 and ALPN `hearthghost-node/1`.
- Uses a Node certificate from `CurrentUser\\My` and HearthGhost CA from
  `CurrentUser\\CA` by exact thumbprint. The CA is a connection-scoped custom
  trust anchor, not a Windows trusted root.
- Rejects missing/ambiguous certificate matches, missing private keys and CNG keys whose export policy allows export/archiving.
- Rebuilds the server certificate chain against the configured HearthGhost CA and rejects endpoint-name mismatch.
- Reuses the existing Node Gateway sequence: `session.open` then `conversation.text` capability request.
- Reuses the existing conversation framing and principal-scoped Persona behavior.
- Added `windows.html` using the shared CharacterViewport, 영희/철수 catalog, VRM renderer and TextConversationController.
- Added a reproducible `windows:assets` helper for AvatarSample A/C and a `windows:dev` Vite workflow.
- Added a Windows GitHub Actions job that restores and builds the WebView2 client on a Windows runner.

## Security decisions

- Windows WebView2 is presentation only; Node authority remains in the native bridge.
- The shell navigates only to one configured loopback HTTP origin and rejects other origins/new windows.
- WebView permission requests are denied in HG-033. Microphone/TTS/notifications must be added through explicit native Windows adapters.
- No PFX path or password input is accepted by the current client.
- Private keys are not serialized to JavaScript, environment variables, repository files or WebView messages.
- Character selection remains behavior/presentation metadata only and cannot mutate Hard Policy, Node trust, grants or credentials.
- Browser builds without the reviewed WebView2 host still have no native mTLS adapter.

## Required physical validation

1. Create/import a reviewed Windows Node certificate whose private key is CNG-backed and non-exportable.
2. Bind `windows-development-01` to that certificate in the Node administration flow.
3. Advertise and grant `conversation.text`.
4. Start `npm run windows:dev` and the WPF shell.
5. Verify TLS 1.3 + ALPN connection over LAN, then over the intended private route/VPN if remote.
6. Verify ordinary text E2E and both 영희/철수 Persona selections.
7. Verify VRM A/C rendering in WebView2 and monitor GPU/memory behavior over a long session.
8. Verify closing or backgrounding the shell removes the active Node/conversation session.

## Follow-up priorities

### HG-034 Windows enrollment

- Generate the Node key in Windows CNG with export disabled.
- Generate CSR without exporting the private key.
- Add an enrollment/status UI comparable to Android HG-014.
- Install the signed certificate chain into CurrentUser stores only after identity checks.

### HG-035 Windows local voice

- Enumerate installed Windows local speech synthesis voices.
- Map 영희/철수 to distinct local voices/tuning when available.
- Add local-only STT only if the selected Windows speech API can be proven not to send media to cloud services.
- Keep text fallback when that guarantee is unavailable.

### HG-036 Windows reminders

- Add Windows-native toast/local scheduling as a separate capability.
- Keep reminder content redacted by default.
- Require explicit local authorization and preserve the Core routing/policy boundary.

### Packaging

- After development E2E is stable, add a packaged static WebView2 asset mode so Vite is not required for normal use.
- Add signed Windows build artifacts only after code-signing/key custody is defined.

## Stop point

HG-033 is considered code-complete only when Python/client/Android/Windows CI are green. Real Windows certificate-store and Core E2E remain physical validation tasks and must not be claimed from CI alone.
