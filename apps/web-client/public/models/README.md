# HearthGhost VRM asset slots

The client recognizes two local VRM asset names:

- `AvatarSample_Y.vrm` → **영희 / Younghee**
- `AvatarSample_C.vrm` → **철수 / Cheolsu**

## Model A / Younghee

`AvatarSample_Y.vrm` is a user-created HearthGhost model made by repository
owner `livingmetal`, who authorized its distribution with this repository on
2026-08-14. It is tracked directly in this directory as HearthGhost model A.

Reviewed identity:

- bytes: `16935148`
- SHA-256: `48af6bf879cadbc4e17431543f795010c9ca2bf31c3ca5e0b450c87b05545c11`
- container: glTF 2.0 / VRM 1.0
- generator: `VRoid Studio 2.14.0`
- creator and distribution authority: repository owner `livingmetal`

The current VRM binary retains default embedded metadata naming
`pixiv VRoid Project` and marking redistribution and modification as
restricted. This does not match the repository owner's stated authorship and
distribution authorization. The repository records the discrepancy rather
than misclassifying Model A as a third-party VRoid sample. A future authoring
export should align the embedded creator and redistribution fields; until then,
the reviewed SHA-256 above identifies the exact owner-authorized binary.

The client asset step validates this identity before Windows or local Android
packaging. `HEARTHGHOST_MODEL_A_PATH` is only a development override for
trying a replacement before committing it.

## Model C / Cheolsu

`AvatarSample_C.vrm` remains fetched at build time from the pinned public
`hirokazuniimoto/virtual-avatar-sdk` redistribution:

- source commit: `114d4336e0ac36bf9c2297b0a93ad7604b13704b`
- Git blob: `4513c2989150c6bd5040f8a3e1b89631efef9a87`

The asset preparation step verifies the Git blob identity before use.

## Runtime

Vite packages the reviewed models into `dist/models/`, and Capacitor copies
them into Android application assets. A normal runtime does not download VRM
models. If model loading fails, the client preserves the built-in DOM
character fallback rather than loading an unreviewed remote replacement.
