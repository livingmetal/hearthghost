# HG-SPIKE-001: Open-source reuse assessment

Status: research recommendation, not an implementation decision

Evaluated: 2026-08-10

Scope: repository and public-source review only; no runtime host access, installation, execution, benchmark, dependency import, or asset import

## Executive recommendation

HearthGhost should reuse narrow, mature runtimes behind HearthGhost-owned ports and keep every authority-bearing boundary in HearthGhost.

HearthGhost-owned:

- policy evaluation, authorization, confirmation, audit semantics, and the Privacy Gateway;
- Node identity, trust, capability grants, revocation, and node-local camera/microphone gates;
- household attention, privacy, memory-retention, and identity rules;
- Tool Proposal-to-execution separation and device credentials;
- renderer-neutral character state and emotion semantics.

Strong reuse candidates:

- VRM rendering: use `@pixiv/three-vrm` below `CharacterRenderer`;
- 2D rendering: use PixiJS if an animated sprite renderer proves to need a scene engine;
- local speech: wrap sherpa-onnx, subject to a separate Korean model and voice license/quality decision;
- smart home: wrap Home Assistant's authenticated APIs as a device-integration backend;
- real-time audio utilities: extract only the demonstrably UI-independent pieces of AIRI's audio pipeline if a later implementation comparison beats a small HearthGhost implementation.

Reference only:

- AIRI for Web/Capacitor character presentation and renderer lifecycle patterns;
- N.E.K.O. for memory workflows and multi-renderer product exploration;
- OpenClaw for gateway, node, approval, and plugin threat-model lessons;
- ClawStage for physical privacy-control and docked-companion ideas;
- Model Context Protocol (MCP) for a possible future external-tool adapter, not as an authority model.

Rejected as foundations are the complete AIRI, N.E.K.O., and OpenClaw runtimes. Each imports a much larger agent, plugin, credential, telemetry, or trust model than HearthGhost needs. ClawStage supplies no licensed implementation to reuse at the inspected revision. No candidate justifies a fork. No current invariant requires a candidate to be reimplemented wholesale.

## Method and constraints

The assessment first treated the repository documents under `docs/architecture`, `docs/security`, and `docs/product`, plus the root and application `AGENTS.md` files, as requirements. External repositories were inspected at exact commits or release tags. Public project documentation was used to interpret, but not override, source evidence.

This spike did not:

- connect to `192.168.55.100` or any runtime host;
- inspect a deployed Home Assistant instance;
- run third-party code or install dependencies;
- benchmark speech or rendering models;
- copy code, models, voices, art, themes, or sample assets;
- add packages, submodules, forks, adapters, or contract changes.

Consequently, runtime performance, Korean recognition quality, voice quality, and on-device thermal behavior remain decision gates rather than conclusions.

## Non-negotiable fit criteria

An external component may sit below a HearthGhost adapter, but it may not collapse these distinctions:

```text
LLM output != Tool authorization
authenticated Node != authorized Capability
discovered Node != trusted Node
Core request != node-local camera/microphone authorization
conversation preference != Hard Policy
Home Assistant service success != HearthGhost policy approval
renderer expression name != Core emotion semantics
```

For sensitive actions the required path remains:

```text
LLM
  -> Tool Proposal
  -> Policy Evaluation
  -> Authorization / Confirmation
  -> Executor
  -> Adapter
  -> Device
```

Missing, stale, ambiguous, revoked, or mismatched authorization must fail closed. A renderer or speech engine can be replaced; the above authority semantics cannot be delegated to one.

## Candidate matrix

Each row has exactly one primary classification. “Maturity” describes suitability of the inspected component, not project popularity.

| Project/component | Subsystem | License at inspected source | Stack | Maturity | Security fit | Integration complexity | Classification | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AIRI complete runtime | Companion/agent platform | MIT code; dependencies/assets separate | TypeScript, Vue, Tauri/Capacitor, Rust | Active, broad monorepo | Poor: imports unrelated agent/plugin/provider/telemetry assumptions | Very high | **REJECT** | Do not make it HearthGhost's application or agent foundation. |
| AIRI `stage-ui-three` | VRM presentation | MIT source; VRM assets separate | Vue, Pinia, TresJS, Three.js, three-vrm | Working lifecycle and cache code | Acceptable only below renderer boundary | High because UI/state packages are coupled | **REFERENCE ONLY** | Learn from loading, cleanup, cache, and tracing; consume three-vrm directly. |
| AIRI `stage-ui-live2d` | Live2D presentation | MIT wrapper; Cubism Core and models have separate proprietary terms | Vue, PixiJS 6, Cubism | Functional but tied to older Pixi and proprietary runtime | Neutral at renderer level | High legal and stack coupling | **REJECT** | Exclude from the initial renderer path. Re-open only after a specific licensed Live2D use case exists. |
| AIRI `pipelines-audio` | Streaming/playback/TTS chunking | MIT source; dependencies separate | TypeScript | Focused package with tests and documented UI independence | Good if capture and retention stay node-local | Medium | **EXTRACT** | Compare its small modules with a native implementation, preserve provenance, and extract only selected code if justified. |
| AIRI `stage-pocket` | Mobile character shell | MIT code; downloaded samples/assets separate | Capacitor, Vue, WebView | Real Android packaging path | Mixed: permissions exist, but app-wide assumptions exceed HearthGhost | High | **REFERENCE ONLY** | Use as evidence for Capacitor/WebView constraints, not as the client base. |
| AIRI placeholder packages | Character core, Home Assistant, pgvector memory | MIT | TypeScript | Empty, WIP, or skeletal at inspected revision | Not assessable | Misleading rather than useful | **REJECT** | Do not treat package names as implemented architecture. |
| N.E.K.O. complete runtime | Companion/agent platform | Apache-2.0 code plus NOTICE; assets/models/services separate | Python 3.11, browser/Electron, JavaScript | Feature-rich and active | Poor: broad automation, credentials, telemetry, and plugin surface | Very high | **REJECT** | Its integrated runtime is not a safe HearthGhost backend or client base. |
| N.E.K.O. renderer code | VRM, Live2D, MMD, PNGTuber | Apache-2.0 code; runtimes/models/motions separate | Browser JavaScript plus Python application | Broad, application-coupled implementations | Acceptable only as isolated renderer research | High | **REFERENCE ONLY** | Study state/motion organization; do not import the coupled renderer layer. |
| N.E.K.O. bundled character assets | Models, motions, art | Unresolved at inspected paths | VRM/VRMA, Live2D archives, images | Technically usable, legally unverified | Privacy-neutral, provenance-poor | High | **REJECT** | Do not copy or redistribute any bundled character asset. |
| N.E.K.O. memory subsystem | Persistent/event/evidence/reflection memory | Apache-2.0 source; embedding models separate | Python, local services/storage | Substantial implementation | Partial: retention and privacy semantics are not HearthGhost's | High | **REFERENCE ONLY** | Reference evidence/review flows after HearthGhost defines memory policy and provenance. |
| N.E.K.O. plugin host/SDK | Plugin marketplace and process execution | Apache-2.0 source; plugin licenses separate | Python, ZeroMQ, subprocesses | Extensive | Poor for HearthGhost's least-authority model | High | **REFERENCE ONLY** | Study lifecycle and compatibility tests; design a narrower capability-scoped host. |
| OpenClaw complete backend | Agent/gateway/session runtime | MIT code; extensions/dependencies separate | TypeScript/Node, native clients | Large, active, operationally mature | Poor: single-trusted-operator and host-tool assumptions differ materially | Very high | **REJECT** | Do not place it behind the Agent adapter as HearthGhost's authority-bearing backend. |
| OpenClaw gateway/node patterns | Gateway, pairing, approvals, remote nodes | MIT | TypeScript plus native clients | Detailed implementation and security docs | Useful lessons, incompatible authority defaults | Medium as research | **REFERENCE ONLY** | Borrow threat-model questions, not its trust semantics. |
| OpenClaw memory/session design | Markdown/SQLite recall and session handling | MIT; embedding/provider terms separate | TypeScript, SQLite | Mature user-facing behavior | Partial: recalled content is not policy and retention differs | Medium as research | **REFERENCE ONLY** | Reference storage and recall UX while preserving HearthGhost privacy/provenance rules. |
| OpenClaw plugin/skill/MCP surface | Tools, extensions, manifests | MIT; every extension/plugin may differ | TypeScript, in-process extensions | Broad ecosystem | Poor: installed extensions are trusted with process privileges | High | **REFERENCE ONLY** | Use its warnings and metadata separation as design input; never treat install/enabled as authorized. |
| ClawStage repository/materials | Companion hardware/product | No repository license found | README, images, schematic PDF | Documentation-only at inspected revision | Physical controls are promising but unverified | Not integrable | **REFERENCE ONLY** | Reference form factor and physical privacy ideas only. |
| `@pixiv/three-vrm` 3.5.3 | VRM runtime | MIT | TypeScript, Three.js | Focused, released library | Good below `CharacterRenderer` | Medium | **USE** | Consume a pinned release and isolate VRM names inside the adapter. |
| PixiJS 8.18.1 | 2D sprite renderer | MIT | TypeScript/WebGL/WebGPU/Canvas | Mature general renderer | Good below `CharacterRenderer` | Low to medium | **USE** | Use only if prototype complexity/performance warrants it; keep a plain sprite implementation possible. |
| sherpa-onnx 1.13.4 | Local STT/TTS/VAD/KWS | Apache-2.0 runtime; each model/voice separate | C/C++ with Android, Java, Kotlin, JS and other bindings | Broad offline runtime with active releases | Good behind node-local speech adapters | Medium | **WRAP** | Preferred shortlist anchor; approve runtime and each model independently. |
| openWakeWord 0.6.0 | Wake word | Apache-2.0 code; bundled models CC BY-NC-SA 4.0 | Python, ONNX/TFLite | Usable but stable release is old and pretrained scope is English | Processing model fits; supplied assets do not | Medium | **REJECT** | Do not use as the default Korean/local wake path. Its model licensing and language coverage are blockers. |
| Home Assistant Core/API 2026.8.1 | Smart-home backend | Apache-2.0 code; integrations vary | Python, WebSocket/REST APIs | Mature integration platform | Good only behind HearthGhost authorization | Medium | **WRAP** | Keep HA as device backend with a least-privilege identity and explicit entity/action allowlists. |
| MCP specification 2026-07-28 | External tool interoperability | Apache-2.0 for new code/spec; legacy contributions may remain MIT; non-spec docs CC BY 4.0 | Protocol/JSON-RPC ecosystem | Released but newly breaking/stateless generation | Protocol does not supply HearthGhost authorization | Medium | **REFERENCE ONLY** | Revisit as an adapter when a concrete external-tool need exists; do not alter v1 contracts now. |

No evaluated component receives **FORK**: none is simultaneously close enough to HearthGhost's boundaries and valuable enough to justify permanent divergence. No evaluated subsystem receives **REIMPLEMENT** as a primary strategy: HearthGhost will implement its domain-specific ports and authority logic, but mature rendering, speech, and smart-home engines should remain external.

## Detailed findings

### AIRI

Inspected revision: [`b230e16b2eeebaa7e14383f0fa1ebbf055c9fbb5`](https://github.com/moeru-ai/airi/tree/b230e16b2eeebaa7e14383f0fa1ebbf055c9fbb5). The monorepo contains multiple applications, packages, and plugins rather than a small embeddable character SDK. The root [MIT license](https://github.com/moeru-ai/airi/blob/b230e16b2eeebaa7e14383f0fa1ebbf055c9fbb5/LICENSE) covers AIRI-authored code, not all linked runtimes, downloaded models, or samples.

The strongest evidence is component-specific:

- [`packages/stage-ui-three`](https://github.com/moeru-ai/airi/tree/b230e16b2eeebaa7e14383f0fa1ebbf055c9fbb5/packages/stage-ui-three) implements useful loading, scene lifecycle, cache, cleanup, and trace patterns. Its Vue, Pinia, TresJS, Three.js, and AIRI workspace dependencies make direct reuse more expensive than consuming three-vrm.
- [`packages/stage-ui-live2d`](https://github.com/moeru-ai/airi/tree/b230e16b2eeebaa7e14383f0fa1ebbf055c9fbb5/packages/stage-ui-live2d) depends on PixiJS 6-era Live2D integration and Cubism. Live2D's proprietary Core and model/publication terms require a separate legal path; AIRI's MIT license cannot grant those rights.
- [`packages/pipelines-audio`](https://github.com/moeru-ai/airi/tree/b230e16b2eeebaa7e14383f0fa1ebbf055c9fbb5/packages/pipelines-audio) contains playback, stream, transcript-buffer, and TTS chunking utilities with tests and an explicit UI-independent goal. It is the one plausible extraction target, but workspace-type dependencies and node-local privacy still require review at extraction time.
- [`packages/core-character/src/index.ts`](https://github.com/moeru-ai/airi/blob/b230e16b2eeebaa7e14383f0fa1ebbf055c9fbb5/packages/core-character/src/index.ts), [`plugins/airi-plugin-homeassistant/src/index.ts`](https://github.com/moeru-ai/airi/blob/b230e16b2eeebaa7e14383f0fa1ebbf055c9fbb5/plugins/airi-plugin-homeassistant/src/index.ts), and [`packages/memory-pgvector/src/index.ts`](https://github.com/moeru-ai/airi/blob/b230e16b2eeebaa7e14383f0fa1ebbf055c9fbb5/packages/memory-pgvector/src/index.ts) are empty, WIP, or skeletal at the inspected revision. They provide no implemented boundary worth adopting.
- [`apps/stage-pocket`](https://github.com/moeru-ai/airi/tree/b230e16b2eeebaa7e14383f0fa1ebbf055c9fbb5/apps/stage-pocket) demonstrates a Capacitor Android shell and native microphone permission handling. Its application graph is much larger than a renderer, and build configuration references externally hosted sample models. Those samples need their own provenance and license review.

AIRI also contains optional analytics integration. Full-application reuse would therefore require a privacy and network-egress audit. Extracting a narrow renderer-independent utility avoids importing that concern.

Conclusion: AIRI is valuable design evidence, not a HearthGhost foundation. Its 3D and mobile work make TypeScript/Web a credible client path, but do not make that technology choice mandatory.

### N.E.K.O.

Inspected revision: [`d07fc42a8e8303a043acb99d031cd159fc711350`](https://github.com/Project-N-E-K-O/N.E.K.O/tree/d07fc42a8e8303a043acb99d031cd159fc711350). The root code is [Apache-2.0](https://github.com/Project-N-E-K-O/N.E.K.O/blob/d07fc42a8e8303a043acb99d031cd159fc711350/LICENSE) with a NOTICE file. The application combines a Python 3.11 backend, browser/Electron UI, provider SDKs, computer/browser automation, vision/audio, memory, Steam integration, and a plugin ecosystem; [`pyproject.toml`](https://github.com/Project-N-E-K-O/N.E.K.O/blob/d07fc42a8e8303a043acb99d031cd159fc711350/pyproject.toml) shows the breadth of the dependency surface.

Renderer code is real but not cleanly separated from product state. Files under [`static/vrm`](https://github.com/Project-N-E-K-O/N.E.K.O/tree/d07fc42a8e8303a043acb99d031cd159fc711350/static/vrm) manage VRM loading, expressions, gaze, orientation, interaction, and compressed VRMA motions. Live2D and other modes expand the surface further. This proves useful interaction patterns, but it does not offer a stable, renderer-neutral package below HearthGhost's `CharacterRenderer` port.

The repository includes VRM files, motion files, images, and archived character assets such as `assets/yui-origin.tar.gz` and `assets/yui-lolita.tar.gz`. No asset-specific license was found beside those archives during inspection. The project README itself warns that application openness does not settle every model, voice, character, or service license. All bundled assets are therefore excluded from reuse.

The memory implementation is substantial: [`app/memory_server`](https://github.com/Project-N-E-K-O/N.E.K.O/tree/d07fc42a8e8303a043acb99d031cd159fc711350/app/memory_server) contains event/evidence, review, refinement, signal extraction, and post-turn flows. It is useful reference material, but HearthGhost must first define retention, subject access/deletion, provenance, trust, and household isolation. Importing the subsystem before those rules would make storage behavior drive policy.

The plugin tree uses a server/SDK, ZeroMQ IPC, marketplace workflows, and task execution. This is broader than HearthGhost's capability-scoped Tool Proposal model. Any third-party process, dependency installation, or subprocess execution would require explicit sandboxing and grants that N.E.K.O.'s application model cannot supply on HearthGhost's behalf.

[`utils/token_tracker/telemetry.py`](https://github.com/Project-N-E-K-O/N.E.K.O/blob/d07fc42a8e8303a043acb99d031cd159fc711350/utils/token_tracker/telemetry.py) enables anonymous token-usage telemetry unless disabled and may derive a stable Steam identity when available. Even if reasonable for N.E.K.O., that default conflicts with HearthGhost's privacy posture. The complete runtime is therefore rejected.

### ClawStage

Inspected repository revision: [`08849c90e18385d11753565ff2f4b5ca160f6f4d`](https://github.com/HooRii-OT/clawstage/tree/08849c90e18385d11753565ff2f4b5ca160f6f4d); public product material: [clawstage.ai](https://clawstage.ai/).

Verified source availability is much narrower than the product description. The inspected repository contains a README, images, and a microphone-mute schematic PDF. It contains no software implementation, firmware, CAD, bill of materials, reproducible build instructions, or LICENSE file. It is therefore not a legally or technically reusable open-source character runtime.

The public site describes a Raspberry Pi 5 device with a square display, camera, dual microphone, speaker, servo, sensors, and physical camera/microphone controls. Those are product claims, not verified source. The form factor, “one identity/multiple shells” framing, and conspicuous physical controls are worth referencing. Any future hardware design must independently verify that a switch cuts the intended power/data path; a selectable microphone power path can otherwise bypass the visible privacy promise.

### OpenClaw

Inspected revision: [`5c308e0ebacfa92a9992d77f342facd0bbcef90e`](https://github.com/openclaw/openclaw/tree/5c308e0ebacfa92a9992d77f342facd0bbcef90e), [MIT license](https://github.com/openclaw/openclaw/blob/5c308e0ebacfa92a9992d77f342facd0bbcef90e/LICENSE).

OpenClaw is a large operational assistant platform with a gateway, sessions, tools, extensions, memory, voice, and remote/native nodes. Its [security documentation](https://github.com/openclaw/openclaw/blob/5c308e0ebacfa92a9992d77f342facd0bbcef90e/SECURITY.md) explicitly treats the model as untrusted, which is a sound starting point. It also assumes a single trusted operator boundary: authenticated gateway callers are operators, paired nodes extend operator execution, tools can execute on the host, and installed extensions run in-process with host privileges. Approvals are operator guardrails rather than a multi-tenant or household authorization system.

That is not HearthGhost's boundary. A paired/authenticated Node still needs separately granted, current, purpose-bound capabilities. Camera permission must exist both in the operating system/node and in HearthGhost authorization. The Core must be unable to manufacture either. OpenClaw's allowlists, local binding defaults, node command controls, and candid threat-model documentation are valuable references, but an adapter cannot cheaply reverse its underlying operator trust model.

OpenClaw's memory design combines human-readable files and indexed recall. This is useful operationally, but recalled content is data, not policy or trusted instruction. HearthGhost would still need provenance, retention, household separation, and instruction/content handling around it. The plugin/skill ecosystem is similarly informative but cannot be imported: plugin metadata, installation, enablement, and permission must be distinct, while OpenClaw extensions are trusted code once loaded.

Conclusion: using OpenClaw behind a HearthGhost Agent adapter would create two overlapping session/tool/node authority systems and make audit completeness difficult to prove. Reject the runtime; reference its threat model and operational lessons.

## Character subsystem recommendation

The HearthGhost boundary should remain:

```text
Application Shell
  -> CharacterViewport
  -> CharacterRenderer
       -> Sprite renderer
       -> VRM renderer
       -> Future renderer
```

The port receives semantic state, not renderer implementation names. For example, `state=speaking` and `emotion=amused` may map to a sprite sequence, VRM expression/blend shape, gaze behavior, or later renderer-specific animation entirely inside the adapter.

### VRM

Use [`@pixiv/three-vrm` 3.5.3](https://github.com/pixiv/three-vrm/tree/v3.5.3) under a HearthGhost VRM renderer. It is a focused MIT library that handles VRM parsing and Three.js integration without importing an agent backend. Pin the release and compatible Three.js version. Keep model loading, expression lookup, animation identifiers, gaze, lip-sync mapping, and cleanup private to the adapter.

VRM runtime code does not license a `.vrm` character. VRM metadata and the source artist's terms can independently restrict commercial use, redistribution, modification, violent/sexual usage, or impersonation. Every production model needs a recorded source, checksum, author, license, allowed-use decision, and embedded-metadata inspection.

Mobile performance is unresolved. A prototype must test cold load, steady-frame time, memory, thermal behavior, WebGL context loss, background/foreground transitions, and portrait/landscape resizing on representative phones/tablets. AIRI proves a Web/Capacitor path is possible, not that it satisfies HearthGhost's target envelope.

### 2D

Use [PixiJS 8.18.1](https://github.com/pixijs/pixijs/tree/v8.18.1) if the sprite prototype needs a retained scene graph, batching, filters, or WebGL/WebGPU acceleration. For a small state-driven character, DOM/CSS, Canvas, or video/image sequences may be lighter; the port must permit that smaller implementation.

Sprite assets, PNG/WebP/WebM sequences, and generated art remain separately licensed. PNGAL or another generator affects provenance, not the right to use its inputs or outputs. The adapter owns state/emotion-to-asset mapping, preload policy, animation interruption, fallback assets, lip-sync frames, and missing-asset behavior.

### Lip sync and character state

AIRI's `model-driver-lipsync` and renderer mappings are reference material, not a stable independent runtime. Start with a renderer-neutral mouth-intensity/viseme event produced from trusted TTS timing or a local audio envelope. The renderer maps that signal to sprite frames or VRM expressions. The Core must never emit filenames, blend-shape names, or animation IDs.

Conversation state and emotion remain orthogonal. Missing or unknown emotion should select a neutral presentation; it must not prevent audio or change policy behavior.

## Mobile implications

A TypeScript Web client makes three-vrm and PixiJS reuse easiest and can be packaged as a PWA or Capacitor WebView. AIRI's `stage-pocket` demonstrates Android packaging and permission bridges, while N.E.K.O. demonstrates browser renderers. Neither settles HearthGhost's final shell.

Trade-offs to validate before an ADR:

| Path | Easier | Harder / risk |
| --- | --- | --- |
| PWA | Deployment, browser debugging, shared desktop/mobile renderer | Background wake, durable microphone access, OS integration, lifecycle variability |
| Capacitor/WebView | Reuse Web rendering plus native permission/audio bridges | WebView GPU variance, bridge complexity, foreground service and store-policy work |
| Native Android shell with embedded renderer | Audio/camera lifecycle and background controls | Two UI stacks or a custom 3D bridge; slower cross-platform iteration |

Portrait should remain character-first. Landscape may reveal context beside the character without changing semantic character contracts. Camera and microphone authorization must be enforced in native/node code even when the UI is a WebView. No raw pre-wake audio should cross the node boundary or be persisted.

## Local STT, TTS, VAD, and wake word

### sherpa-onnx

Inspected release: [`v1.13.4` / `142807252687d81b40d6315f23470a1512a00de3`](https://github.com/k2-fsa/sherpa-onnx/tree/v1.13.4), [Apache-2.0 license](https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.4/LICENSE).

sherpa-onnx provides offline recognizer, TTS, VAD, and keyword-spotting APIs across native and mobile bindings. Android wrappers are visible in [`android/SherpaOnnxAar/sherpa_onnx/src/main/java/com/k2fsa/sherpa/onnx`](https://github.com/k2-fsa/sherpa-onnx/tree/v1.13.4/android/SherpaOnnxAar/sherpa_onnx/src/main/java/com/k2fsa/sherpa/onnx), and the core implementation is under [`sherpa-onnx/csrc`](https://github.com/k2-fsa/sherpa-onnx/tree/v1.13.4/sherpa-onnx/csrc). This breadth supports one wrapped runtime across WTR PRO and Android experiments.

The runtime is not the model. Published Korean ASR and TTS examples make it the best shortlist anchor, but each acoustic model, tokenizer, training dataset, and voice needs independent terms. One referenced Korean Zipformer artifact traces to AIHub/KsponSpeech yet did not present sufficiently clear downstream model licensing in the inspected distribution page. No Korean model or voice is approved by this spike.

On the Ryzen 7 5825U, CPU-first offline operation is plausible but unverified. A later benchmark should measure real-time factor, first-token latency, peak RAM, accuracy on Korean household speech, noise robustness, binary/model size, and concurrency. The adapter must expose failure/timeouts without turning partial transcripts into trusted instructions.

### Wake word

Inspected openWakeWord code revision [`368c03716d1e92591906a84949bc477f3a834455`](https://github.com/dscripka/openWakeWord/tree/368c03716d1e92591906a84949bc477f3a834455) and stable release [`v0.6.0`](https://github.com/dscripka/openWakeWord/tree/v0.6.0). The code is Apache-2.0, but included pretrained models are documented as CC BY-NC-SA 4.0 because of training-data constraints, and the supplied models are English-focused. That combination is unsuitable for a default Korean-capable HearthGhost distribution.

Sherpa-onnx KWS remains in the shortlist because it shares the wrapped runtime, but its selected keyword model still needs provenance, Korean false-accept/false-reject testing, and CPU measurements. Until that decision, use platform-local capture, acoustic echo cancellation/noise suppression where available, VAD, and wake processing as node-owned plumbing rather than importing an assistant platform.

### TTS and voice rights

Sherpa-onnx can host local TTS models, but this spike selects no voice. A voice approval must separately record model license, training-data provenance where disclosed, speaker consent/impersonation constraints, redistribution rights, and whether generated audio can be cached. Hosted-provider fallbacks, if later allowed, require a separate privacy/data-egress decision.

## Agent, memory, tool, and plugin recommendation

No evaluated complete agent backend fits HearthGhost well enough to wrap. AIRI and N.E.K.O. couple companion UI to provider, memory, tool, and plugin behavior. OpenClaw is architecturally sophisticated but its single-operator gateway and trusted-extension model conflicts with household and physical-device authority separation.

HearthGhost should retain a narrow Agent/Orchestrator port whose outputs are proposals and content. It must never receive executor credentials or mutate policy. Session IDs, proposal IDs, decision IDs, execution IDs, Node IDs, and audit correlation IDs must remain traceable across adapters without treating any external session identifier as authorization.

Memory should remain HearthGhost-owned at the policy layer even if storage/index engines are reused later. Required semantics include:

- explicit provenance and confidence;
- household/subject isolation;
- retention, deletion, and export behavior;
- separation of remembered content from instructions and Hard Policy;
- no silent raw ambient audio, camera frames, or unrestricted transcript retention;
- audit linkage without turning the audit log into conversational memory.

MCP may eventually reduce custom protocol work for external tools. The inspected [2026-07-28 specification](https://github.com/modelcontextprotocol/modelcontextprotocol/tree/2026-07-28) is a new, breaking stateless generation. Its [licensing repository](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/2026-07-28/LICENSE) distinguishes Apache-2.0 new spec/code, legacy MIT contributions, and CC BY 4.0 non-spec documentation. More importantly, protocol-level tool discovery or invocation is not policy approval. Keep the v1 Tool Proposal/Policy Decision/authorization contracts unchanged and revisit MCP only for a concrete adapter.

## Home Assistant boundary

Inspected Home Assistant Core release: [`2026.8.1`](https://github.com/home-assistant/core/tree/2026.8.1), [Apache-2.0 license](https://github.com/home-assistant/core/blob/2026.8.1/LICENSE). HearthGhost should not embed or fork Core. It should use an existing Home Assistant deployment as the device-integration backend through authenticated [WebSocket](https://developers.home-assistant.io/docs/api/websocket/) or REST APIs.

The adapter should:

- hold credentials outside the Agent/LLM and use a dedicated least-privilege identity where the deployment permits;
- expose only explicitly mapped entities, domains, and service/action parameters;
- translate a HearthGhost execution authorization into one bounded HA call;
- carry HearthGhost correlation IDs in local audit records and retain the HA request/result context when available;
- time out and fail closed on disconnect, unknown entity/action, malformed result, or stale authorization;
- require HearthGhost confirmation for critical actions even if HA would accept the service call;
- treat HA authentication, entity discovery, or successful execution as neither household consent nor HearthGhost authorization.

Home Assistant integration code, custom components, blueprints, and add-ons can have licenses or security properties distinct from Core. Those become part of the adapter's deployment inventory later.

## Security-fit findings

| External assumption or risk | HearthGhost treatment |
| --- | --- |
| An LLM/tool framework can call a tool directly | Adapter emits Tool Proposals only; Policy, authorization, and Executor remain separate. |
| A logged-in gateway user is a trusted operator | Authentication identifies a principal; it does not grant device capabilities. |
| Pairing a node grants its remote commands | Pairing establishes identity; each capability is separately granted, scoped, expiring/revocable, and checked locally. |
| OS camera/microphone permission is enough | OS permission and HearthGhost node-local authorization are both required. Core cannot mint the latter. |
| Continuous microphone/camera streams are normal agent inputs | Wake/VAD and capture gates stay on-node; no pre-wake raw audio or ambient media is sent or retained. |
| Plugin installation implies trust | Discovery, installation, enablement, declared capability, grant, and per-execution authorization are distinct. |
| In-process extensions share host authority | Avoid for untrusted plugins; future host requires isolation and capability-scoped IPC. |
| Provider or HA token is available to the agent | Credentials belong to adapters/executors and are never included in model context. |
| Recalled text is trustworthy context | Memory content retains provenance and is not instruction, policy, or authorization. |
| Analytics is anonymous enough by default | Telemetry and all network egress are opt-in, documented, and independently disableable. |

No reviewed project can replace HearthGhost's Privacy Gateway or make a direct `LLM -> Tool -> Device` path acceptable. Character-only code may still be safe to reuse because it can be isolated from authority and credentials.

## License and asset findings

### Code licenses

- MIT (AIRI, OpenClaw, three-vrm, PixiJS): retain copyright and license notices in distributions containing the software. No source-disclosure or copyleft requirement is imposed by MIT itself; modifications remain under the distributor's chosen terms subject to the notice.
- Apache-2.0 (N.E.K.O., sherpa-onnx, openWakeWord code, Home Assistant Core): retain license/notices, mark modified files where required, and observe the patent-license/termination terms. It is permissive and does not impose copyleft source disclosure.
- MCP: preserve the license applicable to the exact file/history; the repository documents a transition rather than one blanket license for every historic contribution/document.
- ClawStage: no LICENSE was found, so default copyright applies. Public visibility does not grant copying, modification, or redistribution rights.

These are implementation observations, not legal advice. A dependency/license scan and notice-generation step is still required before distribution.

### Art and assets

Code licenses do not automatically cover character art, VRM/Live2D models, animations, sound effects, fonts, themes, screenshots, or externally downloaded samples. AIRI's sample URLs, N.E.K.O.'s archived models/motions, and ClawStage's images/schematic require independent terms. Unclear assets are not reusable.

Live2D Cubism Core is proprietary and Live2D model rights remain separate. Depending on product and publication mode, additional agreements or fees may apply. This is why Live2D is rejected for the initial path even when a wrapper is MIT or Apache-2.0.

### Models and voices

Every STT, TTS, wake, embedding, and vision artifact needs an inventory containing source URL, exact revision, hash, model license, training-data/license statement where available, redistribution decision, supported languages, and intended runtime use. Runtime Apache-2.0 does not make a model Apache-2.0.

Voice review additionally needs speaker/performer consent and impersonation restrictions. Noncommercial, research-only, share-alike, attribution, or unclear-training-data assets must not enter a redistributable default bundle without an explicit decision.

## Maintenance and supply-chain implications

The focused libraries are easier to pin and audit than full companion platforms. AIRI, N.E.K.O., and OpenClaw each carry thousands of files and broad JavaScript/Python/native/plugin dependency graphs. N.E.K.O. also contains bundled archives/wheels and a CosyVoice submodule; complete reuse would expand both the software bill of materials and provenance burden. AIRI build paths that fetch remote models, N.E.K.O. plugin-market installation, and OpenClaw trusted in-process extensions are all incompatible with an unreviewed offline build/runtime path.

Any later adoption should require:

- exact version/commit pins and lock files;
- checksums and an SBOM for native binaries, packages, models, and assets;
- per-artifact license and provenance records;
- reproducible or reviewable builds without arbitrary install scripts;
- vulnerability/advisory monitoring and an update/rollback policy;
- no implicit telemetry, dynamic plugin install, or model download at runtime;
- offline behavior and egress tests;
- adapter contract tests that prove fail-closed behavior when the dependency fails or changes.

Recent commits demonstrate maintenance activity, not API stability. Major upgrades—especially Three.js/WebGL stacks, native ONNX runtimes, Home Assistant APIs, and the new MCP generation—need isolated compatibility tests before rollout.

## Architecture impact and decision sequence

Reuse influences but does not finalize these choices:

1. `three-vrm` plus PixiJS favors a TypeScript/Web character layer. A native shell can still host it, and the renderer-neutral port prevents the Core from depending on Web technology.
2. Capacitor makes reuse of Web renderers easier, while a native Android shell makes background audio, permission state, and node-local gating easier to control. Prototype both lifecycle risks before choosing.
3. sherpa-onnx favors a shared native inference runtime across the WTR PRO and Android, but a model/voice decision must precede packaging.
4. Home Assistant's API favors a separately deployed backend adapter, not embedded Core code or direct LLM integration.
5. Rejecting complete agent platforms keeps HearthGhost's existing Agent, Tool Proposal, Policy, Executor, Node, Capability, and Audit contracts authoritative.
6. Deferring MCP avoids encoding a fast-moving external protocol into v1 contracts before an actual integration requires it.

Recommended sequence before implementation:

1. Define renderer and speech benchmark acceptance criteria without changing domain contracts.
2. Prototype one sprite and one VRM character on representative Android devices in portrait and landscape.
3. Evaluate a pinned sherpa-onnx build with separately cleared Korean ASR/KWS/TTS artifacts on WTR PRO-class CPU and one phone/tablet.
4. Record model/voice/asset provenance and licenses before packaging any artifact.
5. Write ADRs from measured results, then implement narrow adapters.
6. Introduce Home Assistant first with read-only state, then a small low-risk action allowlist and explicit negative authorization tests.
7. Revisit MCP or a plugin host only when a concrete integration cannot be served cleanly by the existing Tool adapter boundary.

## Proposed future ADRs

- Character client shell: PWA, Capacitor, or native Android host.
- VRM renderer dependency and supported VRM/Three.js version matrix.
- 2D renderer threshold: DOM/Canvas versus PixiJS.
- Character asset provenance, redistribution, and embedded VRM-license policy.
- Node-local audio pipeline and Android background/wake strategy.
- Korean STT/KWS model selection and CPU acceptance envelope.
- Local TTS voice selection, consent, and caching policy.
- Home Assistant authentication, entity/action allowlist, and audit mapping.
- Memory storage/index choice after retention and provenance semantics are fixed.
- External tool interoperability/MCP adoption criteria.
- Plugin isolation and supply-chain policy, if third-party plugins become a real requirement.

## Open questions

- Which Android device classes and browsers/WebViews define the minimum renderer performance target?
- What Korean wake phrase, household acoustic conditions, and false-accept/false-reject thresholds are acceptable?
- Which Korean ASR/TTS artifacts have both acceptable quality and unambiguous redistribution/data provenance?
- Is offline-only operation mandatory for every speech path, or may explicitly consented cloud fallback exist?
- What Home Assistant principal/permission granularity is available in the intended deployment without inspecting it during this spike?
- Which critical smart-home actions require re-authentication versus conversational confirmation?
- What character and voice assets are owned or licensed for redistribution?
- Does a concrete external tool require MCP strongly enough to justify an adapter after the 2026-07-28 protocol change?

## Reproducibility ledger

| Project | Source | Inspected revision/tag | Primary evidence paths |
| --- | --- | --- | --- |
| AIRI | https://github.com/moeru-ai/airi | `b230e16b2eeebaa7e14383f0fa1ebbf055c9fbb5` | `LICENSE`, `packages/stage-ui-three`, `packages/stage-ui-live2d`, `packages/pipelines-audio`, `packages/core-character/src/index.ts`, `apps/stage-pocket`, `plugins/airi-plugin-homeassistant/src/index.ts`, `packages/memory-pgvector/src/index.ts` |
| N.E.K.O. | https://github.com/Project-N-E-K-O/N.E.K.O | `d07fc42a8e8303a043acb99d031cd159fc711350` | `LICENSE`, `NOTICE`, `README.md`, `pyproject.toml`, `static/vrm`, `app/memory_server`, `plugin`, `utils/token_tracker/telemetry.py`, `assets` |
| ClawStage | https://github.com/HooRii-OT/clawstage | `08849c90e18385d11753565ff2f4b5ca160f6f4d` | repository root tree, `README.md`, images, microphone schematic PDF; no license or implementation found |
| OpenClaw | https://github.com/openclaw/openclaw | `5c308e0ebacfa92a9992d77f342facd0bbcef90e` | `LICENSE`, `README.md`, `SECURITY.md`, node/tool/memory/plugin documentation and implementation trees |
| three-vrm | https://github.com/pixiv/three-vrm | `v3.5.3`, commit `54e050311b9a27881da21ab842e15380bb512ad8` | `LICENSE`, packages and examples at tag |
| PixiJS | https://github.com/pixijs/pixijs | `v8.18.1`, commit `8f42bb760872ed6652775d00a4de448ac277e783` | `LICENSE`, packages at tag |
| sherpa-onnx | https://github.com/k2-fsa/sherpa-onnx | `v1.13.4`, commit `142807252687d81b40d6315f23470a1512a00de3` | `LICENSE`, `sherpa-onnx/csrc`, Android AAR/KWS examples, model documentation |
| openWakeWord | https://github.com/dscripka/openWakeWord | head `368c03716d1e92591906a84949bc477f3a834455`; stable `v0.6.0` / `c8ef6912c5feccf1037b852d9bc6c7ed644135ba` | `LICENSE`, `README.md`, pretrained-model documentation |
| Home Assistant Core | https://github.com/home-assistant/core | `2026.8.1`, commit `53998d7710b4ac280658511c24a2a3e2651f9873` | `LICENSE`, developer WebSocket and permission/context documentation |
| Model Context Protocol | https://github.com/modelcontextprotocol/modelcontextprotocol | `2026-07-28`, commit `5f5440bb26a62e2cf3440b92da5a667efa03b267` | `LICENSE`, specification and release documentation |

## Decision summary

The immediate sourcing posture is intentionally small: use focused renderers, wrap a focused offline speech runtime and Home Assistant, consider extracting one narrow audio utility package, and treat large companion/agent platforms as research. HearthGhost still owns the seams that make a household assistant safe. No contradiction with the HG-001 v1 contracts was found, so this spike makes no contract change.
