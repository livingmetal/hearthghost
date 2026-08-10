# ADR-0005: Web-first client foundation with native-owned Node security

## Status

Accepted

## Context

HG-SPIKE-002 evaluated a browser-runnable TypeScript client, Android packaging,
and renderer candidates. HearthGhost needs one responsive portrait/landscape
character surface without moving Node identity, private keys, provider secrets,
or trust decisions into web code. The first client milestone must also remain
reversible: no Android permission, production listener, or media decision is
needed to prove the text-only path.

## Decision

Use a TypeScript/Vite web application for the shared client UI and development
runtime. Use a Capacitor Android shell as the intended packaging direction, but
do not generate or ship the native project until a scoped milestone validates
the bridge and Android build on representative devices.

Put Node credentials and mutual-TLS connection ownership behind a narrow
platform port. Native implementations may expose an opaque credential reference
and public connection status to JavaScript; they must never expose private key
material. A browser development adapter must fail clearly when secure Node
transport is unavailable. It must not replace mTLS with plaintext or silently
grant enrollment, trust, or capabilities.

Keep `CharacterViewport` and `CharacterRenderer` renderer-neutral. Adopt
Three.js plus `@pixiv/three-vrm` as the first real renderer, loaded behind that
interface. Use a dependency-free DOM/Canvas placeholder for initial 2D and test
behavior. Do not add PixiJS until a concrete 2D asset pipeline demonstrates a
need for it. Target conservative WebGL behavior first; WebGPU is not required.

The renderer receives only validated semantic conversation state and emotion.
It does not receive credentials, trust administration, Policy Decisions, Tool
proposals, or provider configuration.

Treat foreground/background transitions and process loss as connection
lifecycle events. A resumed client re-evaluates Node state and creates a new
technical session when necessary. Node sessions and conversation sessions stay
distinct. Store no secrets in browser persistence.

The first slice requests no camera, microphone, location, or background-sensing
permission. The UI still shows explicit privacy and Node trust status, works in
portrait and landscape, supports touch/text interaction, and does not depend on
animation to communicate state.

## Consequences

Positive:

- browser and Android packaging can reuse one UI and renderer boundary;
- secure credential handling remains replaceable and native-owned;
- an isolated fake platform adapter can exercise lifecycle behavior without a
  physical device or weaker transport;
- Three/VRM can evolve without coupling Core or the app shell to renderer APIs;
- text-only development does not create media permission or cloud-media risk.

Costs and constraints:

- the browser development build cannot itself be the trusted production Node
  transport;
- a future Android milestone must implement and review the native bridge,
  Keystore/KeyChain selection, certificate lifecycle, and real device recovery;
- the initial VRM bundle is material and must be lazy-loaded and measured on
  representative Android hardware;
- a release needs a generated dependency notice and renewed license and
  vulnerability review.

## Alternatives considered

### Standalone PWA as the trusted Node

Rejected. Browser client-certificate selection and page lifecycle do not give
the application a sufficient native-owned credential and persistent Node
lifecycle boundary.

### Fully native Android UI and renderer

Deferred. It duplicates the web development surface before evidence shows a
native rendering or interaction requirement. The platform port preserves this
option.

### PixiJS for the first 2D renderer

Rejected for now. No approved 2D asset pipeline needs its scene graph, while it
adds a second renderer dependency graph and exposed compatibility friction in
the spike.

### Renderer-specific state in Core

Rejected. It would bind domain contracts to blendshapes, clips, or sprite names
and make alternate renderers unsafe to substitute.

## Security / Privacy impact

Private Node keys stay non-exportable behind the platform adapter where the
platform supports it. Provider credentials remain server-side only. The client
cannot auto-enroll, auto-trust, auto-grant, or downgrade transport. No renderer
or web persistence layer receives secret material. Media remains denied and no
media permission is introduced by this decision.

## Evidence and follow-up

The measurements, versions, licenses, lifecycle sources, and remaining device
gaps are recorded in `docs/research/hg-spike-002-client-runtime.md`. HG-007 may
implement the platform contract and fake/browser adapters. Generating the
Android project, provisioning credentials, binding a listener, or requesting
media permissions requires separately scoped review.
