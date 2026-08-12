# HearthGhost VRM asset slots

The client recognizes two local VRM asset names:

- `AvatarSample_Y.vrm` → **영희 / Younghee**
- `AvatarSample_C.vrm` → **철수 / Cheolsu**

## Model A / Younghee

`AvatarSample_Y.vrm` is the user-created, redistributable HearthGhost model A
asset and is intended to be tracked directly in this directory.

Reviewed identity:

- bytes: `16935148`
- SHA-256: `48af6bf879cadbc4e17431543f795010c9ca2bf31c3ca5e0b450c87b05545c11`
- container: glTF 2.0 / VRM 1.0

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
