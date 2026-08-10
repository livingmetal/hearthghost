# HG-SPIKE-002 Client Runtime and Character Evidence

## Question

What is the smallest reversible client foundation that can provide a responsive
character UI on phones/tablets while preserving the existing per-Node mTLS,
credential, lifecycle, and local-permission boundaries?

This spike does not request Android permissions, capture media, issue
credentials, create production PKI, or establish a production listener.

## Environment and method

- Date: 2026-08-11 KST.
- Runner: WTR PRO-class Linux host, AMD Ryzen 7 5825U (8 cores / 16 threads),
  14 GiB RAM, rootless Podman 5.6.0.
- Toolchain image: `node:22-bookworm-slim`, pulled fresh.
- Isolation: no host network mode, privileges, devices, Docker/Podman socket,
  secrets, or broad mounts. The final import probes used `--network none`, a
  read-only root filesystem, all capabilities dropped, and
  `no-new-privileges`.
- No ADB installation or connected Android device was available. Frame rate,
  GPU memory, Android process RSS, APK size, suspend/resume on device, and touch
  latency therefore remain unmeasured.

The repository-local spike builds renderer-neutral TypeScript contracts against
both VRM and PixiJS candidates. It proves dependency resolution, strict project
type checking, production bundling, and isolated module import. It does not
claim that a Node module import predicts browser rendering performance.

## Candidate versions observed

The npm `latest` metadata was inspected on the spike date and exact versions
were locked for repeatability.

| Candidate | Version | License | npm unpacked size |
| --- | ---: | --- | ---: |
| Capacitor Core / Android | 8.5.0 | MIT | 374,298 / 447,682 bytes |
| Three.js | 0.185.1 | MIT | 23,172,772 bytes |
| `@pixiv/three-vrm` | 3.5.5 | MIT | 2,499,824 bytes |
| PixiJS | 8.19.0 | MIT | 72,415,382 bytes |
| Vite | 8.2.1 | MIT | 2,338,849 bytes |
| TypeScript | 7.0.2 | Apache-2.0 | 2,497,498 bytes |
| `@types/three` | 0.185.4 | MIT | 1,831,296 bytes |

All primary candidates showed recent npm publication activity in July or August
2026. The locked spike graph contains 95 package entries: 54 MIT, 23
Apache-2.0, 3 BSD-3-Clause, 2 ISC, 12 MPL-2.0, plus the package root without a
license field. This is a development spike inventory, not approval to ship the
entire graph. A release needs a generated dependency notice and a fresh license
and vulnerability review.

## Build and memory observations

A clean, pulled, no-cache container build installed 53 packages and performed
TypeScript validation plus both production bundles.

| Observation | Result |
| --- | ---: |
| Clean validation image build | 15.40 s wall time |
| Build-process peak RSS | 192,540 KiB |
| VRM candidate build | 328 ms |
| VRM candidate bundle | 774,208 bytes; 172.77 kB gzip |
| Pixi candidate build | 328 ms |
| Pixi emitted files | 700 KiB on disk; main chunk 248,400 bytes |
| VRM isolated import | 0.27 s wall; 49,304 KiB peak RSS |
| Pixi isolated import | 0.25 s wall; 50,184 KiB peak RSS |
| Installed `node_modules` | 227,256 KiB on disk |

The first strict type check failed. Three.js requires a separately versioned
`@types/three` package, and the combined latest PixiJS/TypeScript/WebGPU
declarations reported third-party library conflicts. Adding the matching Three
types and limiting `skipLibCheck` to dependency declarations produced a clean
project check. This is useful integration-cost evidence: version updates need a
locked compatibility test, and adding both renderer stacks carries avoidable
type and dependency surface.

## Web/PWA

Strengths:

- one renderer and layout implementation can serve desktop development and the
  Android shell;
- CSS media/container queries naturally support portrait and landscape;
- Pointer Events support touch without a command-oriented native UI rewrite;
- `visibilitychange`, `freeze`, `resume`, `pagehide`, and restoration state can
  suspend animation and reconnect safely.

Limits:

- browsers may freeze or discard a page under resource pressure; the client
  must persist only non-secret view/session hints and treat connections as
  replaceable;
- a PWA does not provide an adequate application-owned abstraction over Android
  hardware-backed credentials and Node mTLS lifecycle;
- browser/client-certificate UX and selection are not sufficient as the primary
  persistent household Node provisioning model.

Conclusion: keep a browser-runnable web client for development and UI reuse, but
do not treat a standalone PWA as the trusted Android Node boundary.

## Capacitor-style native shell and Android WebView

Capacitor keeps native Android projects as source artifacts and exposes small
native plugins to the web layer. Its App API maps foreground/background state
to Android lifecycle callbacks. This fits a reversible split:

```text
web UI and CharacterViewport
  -> narrow typed native bridge
  -> Android Node transport / credential adapter
  -> Android Keystore or KeyChain reference
```

Android Keystore can keep key material non-exportable and may bind it to secure
hardware. Android WebView also exposes a host callback for client-certificate
requests; the default is to cancel, and the host must explicitly select and
provide the key/certificate. These facts favor a native-owned connection and
credential reference rather than passing private material into JavaScript.

The native bridge must expose lifecycle/status operations, never raw private
keys. Future camera and microphone plugins require their own STOP-gated design;
they are not generic bridge methods and are not part of this spike.

Conclusion: a web-first application inside a Capacitor Android shell is the
best current packaging direction, but HG-007 should initially define the
platform port and fake/browser adapter before generating a full Android project.

## Renderer evidence

### Three.js plus `@pixiv/three-vrm`

- Directly supports the approved VRM direction and keeps model semantics inside
  a renderer adapter.
- Active 3.x maintenance and MIT licensing were observed.
- The representative bundled candidate is larger than the Pixi main chunk, but
  there is no second renderer stack and no need to translate a VRM character to
  sprites.
- WebGPU support exists but is not needed for the first slice; WebGL remains the
  conservative compatibility target until device evidence justifies otherwise.

Recommendation: use Three.js plus `@pixiv/three-vrm` behind
`CharacterRenderer`, lazy-loaded by `CharacterViewport`.

### PixiJS

- Mature, active, MIT-licensed 2D renderer with WebGL/WebGPU and an experimental
  Canvas fallback.
- Useful if a designed 2D asset pipeline later needs sprite batching, filters,
  or large scene composition.
- No such requirement exists for HG-008. Adding it now increases the locked
  graph and already exposed type-compatibility friction.

Recommendation: do not adopt PixiJS now. A simple DOM/Canvas placeholder can
implement the optional 2D renderer contract until real assets prove Pixi's
value.

## Layout, input, and lifecycle direction

- `CharacterViewport` owns only sizing and renderer lifecycle.
- Portrait keeps the character central with status at the top/edges and text
  input at the bottom.
- Landscape uses a bounded side conversation panel while retaining the same
  viewport and semantic events.
- Touch activates text input or explicit UI actions; it does not grant Node
  trust or capabilities.
- On hidden/pause, stop animation and close or suspend replaceable connections.
  On resume, re-evaluate current Node/session state before reconnecting. Never
  infer that a prior browser page implies a still-valid technical session.

## Security conclusions

- Node identity, private keys, and mTLS remain native/server transport concerns;
  JavaScript receives public status and opaque credential references only.
- The web client never receives provider API credentials.
- A native shell does not auto-enroll, auto-trust, or auto-grant capabilities.
- Node session reconnect and future conversation restoration remain separate.
- No renderer may receive trust, credential, Policy, or Tool execution objects;
  it consumes semantic character state and emotion only.
- No camera, microphone, location, background sensing, or cloud media capability
  was exercised.

## Evidence-backed recommendation

Choose a TypeScript/Vite web application with a renderer-neutral
`CharacterViewport`, Three.js plus `@pixiv/three-vrm` as the first real renderer,
and a Capacitor Android shell as the packaging/native-integration direction.
Keep the Node transport and credential store behind an explicit platform port.
Do not add PixiJS, media permissions, or a generated Android project until a
scoped milestone provides device evidence and reviews the native bridge.

## Sources reviewed

- [Capacitor documentation](https://capacitorjs.com/docs)
- [Capacitor App lifecycle API](https://capacitorjs.com/docs/apis/app)
- [Capacitor plugin guidance](https://capacitorjs.com/docs/plugins/creating-plugins)
- [Capacitor repository and MIT license](https://github.com/ionic-team/capacitor)
- [Android Keystore](https://developer.android.com/privacy-and-security/keystore)
- [Android WebView client-certificate callback](https://developer.android.com/reference/kotlin/android/webkit/WebViewClient#onReceivedClientCertRequest(android.webkit.WebView,android.webkit.ClientCertRequest))
- [Page Lifecycle API](https://developer.chrome.com/docs/web-platform/page-lifecycle-api)
- [`@pixiv/three-vrm` repository and releases](https://github.com/pixiv/three-vrm)
- [PixiJS v8 overview](https://pixijs.com/blog/pixi-v8-launches)
- npm registry metadata for each exact package version listed above

## Remaining evidence gaps

- representative low/mid/high Android tablet rendering FPS and thermal behavior;
- WebView versus Chrome GPU/driver differences;
- Android process and GPU memory with an approved VRM asset;
- touch latency, rotation, process death, and background/foreground recovery;
- Android Studio/Gradle build time and APK/AAB size;
- concrete secure enrollment and key-rotation UX.

These gaps do not block a small browser-first foundation. They do block claims
that a chosen asset, quality level, or Android binary is production-ready.
