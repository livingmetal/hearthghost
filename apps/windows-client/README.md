# HearthGhost Windows development client

The Windows client is a first-class development surface for the shared HearthGhost web UI, VRM renderer and conversation protocol. It uses WPF + WebView2 only as the native shell. Core authentication and conversation traffic are performed by the native .NET bridge over the same TLS 1.3 / `hearthghost-node/1` protocol used by the Android Node.

## Prerequisites

- Windows 11 or a supported Windows 10 build with the WebView2 Runtime.
- .NET 10 SDK.
- Node.js matching the web-client development baseline.
- A reviewed HearthGhost Node certificate in `CurrentUser\\My` with a CNG-backed non-exportable private key.
- The HearthGhost development CA certificate in `CurrentUser\\CA`.
- The Windows Node must be enrolled/trusted and granted `conversation.text` on Core.

The current Windows foundation deliberately does **not** import PFX files or accept a private-key path. The Node private key must stay in the Windows certificate/key store.

## Start the shared UI

From `apps/web-client`:

```powershell
npm ci
npm run windows:dev
```

`windows:dev` validates the tracked AvatarSample Y model, retrieves the pinned
AvatarSample C VRM and AIRI `idle_loop.vrma`, verifies their exact identities,
writes build-fetched assets only into the local `public` presentation tree,
and starts Vite on loopback. The running Windows client does not fetch those
character assets from GitHub.

## Configure the native Node

In a separate PowerShell window:

```powershell
$env:HEARTHGHOST_WINDOWS_CERT_THUMBPRINT = "<CurrentUser\\My node certificate SHA-1 thumbprint>"
$env:HEARTHGHOST_WINDOWS_CA_THUMBPRINT   = "<CurrentUser\\CA HearthGhost CA SHA-1 thumbprint>"
$env:HEARTHGHOST_WINDOWS_CORE_HOST       = "192.168.55.100"
$env:HEARTHGHOST_WINDOWS_CORE_PORT       = "38443"
$env:HEARTHGHOST_WINDOWS_NODE_ID         = "windows-development-01"
$env:HEARTHGHOST_WEB_DEV_URL             = "http://127.0.0.1:5173/windows.html"
```

Do not put certificate private keys, PFX passwords or provider credentials in these variables. Only public identifiers and certificate thumbprints belong here.

The CA stays outside the Windows trusted-root store. The native client loads it
by exact thumbprint from `CurrentUser\\CA` and builds a private custom trust
chain for the configured Core connection only.

## Run the shell

From the repository root:

```powershell
dotnet run --project apps/windows-client/HearthGhost.WindowsClient.csproj
```

The WebView2 shell accepts bridge messages only from the configured loopback origin. WebView permission requests are denied in this first foundation; Windows microphone/TTS/notifications will be added as separate native capabilities instead of silently using browser/cloud services.

## Expected first-run behavior

- `Connect` opens a native TLS 1.3 Node session.
- Core must trust the Node and grant `conversation.text` before Send or character selection is enabled.
- Character appearance and the VRM base idle are rendered locally by the shared web renderer.
- Conversation history is in-memory only and clears when the page closes.

## Not implemented yet

- Windows non-exportable key generation + CSR/enrollment UI.
- Windows local-only STT/TTS adapter.
- Windows toast reminders.
- Packaged/offline static WebView2 distribution. The current shell intentionally targets the loopback Vite development server for fast iteration.
- Physical Windows certificate-store/Core E2E validation.
