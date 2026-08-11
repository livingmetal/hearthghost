# HearthGhost VRM sample asset slots

The client recognizes two local VRM asset names:

- `AvatarSample_A.vrm` → **영희 / Younghee**
- `AvatarSample_C.vrm` → **철수 / Cheolsu**

## Android APK build provenance

The Android container build downloads these two sample files before the Vite/Capacitor build from the public `hirokazuniimoto/virtual-avatar-sdk` redistribution at the pinned source commit:

- source commit: `114d4336e0ac36bf9c2297b0a93ad7604b13704b`
- AvatarSample_A Git blob: `2ab43eef01826a3f93ab92e4174473efd473ae98`
- AvatarSample_C Git blob: `4513c2989150c6bd5040f8a3e1b89631efef9a87`

`containers/android/Containerfile` downloads only those fixed paths and verifies each file with `git hash-object` before the client build. A changed or substituted upstream file therefore fails the APK build instead of silently entering a release.

Vite copies the verified files into `dist/models/`, and Capacitor copies them again into Android assets. The container build verifies both copies exist before Gradle assembles the APK.

A normal runtime never downloads a VRM model. `/models/AvatarSample_A.vrm` and `/models/AvatarSample_C.vrm` are APK-local WebView assets. If model loading still fails on a device, the client preserves the built-in DOM character rather than loading a remote replacement.

For a developer build outside the Android container, the same official samples may instead be placed in this directory manually under the exact filenames above.

## License note

AvatarSample A–Z are not CC0. pixiv/VRoid retains copyright. The official VRoid Hub conditions for the VRoid Project sample models permit use and redistribution for the referenced samples; those conditions must be re-checked before redistributing a release if upstream terms change.

The public redistribution source above is not treated as an authority for licensing. Its bytes are pinned only as a reproducible acquisition path; the applicable usage rights come from the VRoid model conditions.

Official model names and terms must remain distinguishable from HearthGhost's fictional character names: `영희` and `철수` are HearthGhost presentation/persona labels, not official VRoid model names.
