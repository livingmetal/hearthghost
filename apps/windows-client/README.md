# HearthGhost Windows development client

The Windows client is a first-class development surface for the shared HearthGhost web UI, VRM renderer and conversation protocol. It uses WPF + WebView2 only as the native shell. Core authentication and conversation traffic are performed by the native .NET bridge over the same TLS 1.3 / `hearthghost-node/1` protocol used by the Android Node.

## Prerequisites

- Windows 11 or a supported Windows 10 build with the WebView2 Runtime.
- .NET 10 SDK.
- Node.js matching the web-client development baseline.
- A reviewed HearthGhost Node certificate in `CurrentUser\\My` with a CNG-backed non-exportable private key.
- The HearthGhost development CA certificate in `CurrentUser\\Root`.
- The Windows Node must be enrolled/trusted and granted `conversation.text` on Core.

The current Windows foundation deliberately does **not** import PFX files or accept a private-key path. The Node private key must stay in the Windows certificate/key store.

## Start the shared UI

From `apps/web-client`:

```powershell
npm ci
npm run windows:dev
```

`windows:dev` retrieves the pinned AvatarSample A/C VRMs and the pinned AIRI
`idle_loop.vrma`, verifies their exact Git blob identities, writes them only
into the local `public` presentation tree, and starts Vite on loopback. The
running Windows client does not fetch those character assets from GitHub.

## Configure the native Node

In a separate PowerShell window:

```powershell
$env:HEARTHGHOST_WINDOWS_CERT_THUMBPRINT = "<CurrentUser\\My node certificate SHA-1 thumbprint>"
$env:HEARTHGHOST_WINDOWS_CA_THUMBPRINT   = "<CurrentUser\\Root HearthGhost CA SHA-1 thumbprint>"
$env:HEARTHGHOST_WINDOWS_CORE_HOST       = "192.168.55.100"
$env:HEARTHGHOST_WINDOWS_CORE_PORT       = "38443"
$env:HEARTHGHOST_WINDOWS_NODE_ID         = "windows-development-01"
$env:HEARTHGHOST_WEB_DEV_URL             = "http://127.0.0.1:5173/windows.html"
```

Do not put certificate private keys, PFX passwords or provider credentials in these variables. Only public identifiers and certificate thumbprints belong here.

## Run the shell

From the repository root:

```powershell
dotnet run --project apps/windows-client/HearthGhost.WindowsClient.csproj
```

## Optional validated startup updates

The development installer may place `scripts/Start-HearthGhost.ps1` at its
installation root and configure these per-user, non-secret variables:

```powershell
[Environment]::SetEnvironmentVariable(
    "HEARTHGHOST_WINDOWS_AUTO_UPDATE", "1", "User"
)
[Environment]::SetEnvironmentVariable(
    "HEARTHGHOST_WINDOWS_UPDATE_SOURCE", "C:\path\to\hearthghost", "User"
)
[Environment]::SetEnvironmentVariable(
    "HEARTHGHOST_WINDOWS_UPDATE_BRANCH", "codex/hg-039-natural-idle-motion", "User"
)
[Environment]::SetEnvironmentVariable(
    "HEARTHGHOST_WINDOWS_CODE_SIGNING_THUMBPRINT", "<PUBLIC SHA-1 THUMBPRINT>", "User"
)
```

On launch, the script fetches only that allowlisted branch from `origin`,
checks out the exact remote commit into a temporary detached Git worktree,
recreates dependencies, runs the complete client tests, fetches and verifies
the pinned presentation assets, builds the web client, and publishes the native
Windows shell. Only a fully validated result replaces the installed `web` and
`native` directories. The prior installation is retained as
`web.previous`/`native.previous`; any pre-install validation failure keeps and
starts the prior build. `UPDATE_STATUS.json` and `UPDATE_LOG.txt` contain public
build diagnostics. Common provider keys, access tokens, private keys, secrets,
and passwords are removed from the child build environment before any remote
source is built, and embedded credentials in the origin URL are rejected.
If the validated build cannot start its loopback UI or native process, the
launcher restores and starts the retained prior installation automatically.
When the current native executable is signed, the replacement must be signed
and verified with the same CurrentUser certificate. A different explicit
development signer may be selected by its public thumbprint; private key
material is never exported or copied.

The launcher never discovers or follows an arbitrary newest branch. Advancing
the development channel requires an explicit update to
`HEARTHGHOST_WINDOWS_UPDATE_BRANCH`. Use `-SkipUpdate` for recovery and
`-UpdateOnly` to validate/install without opening the client.

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
