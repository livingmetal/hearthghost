# HearthGhost VRM sample asset slots

The client recognizes two local VRM asset names:

- `AvatarSample_A.vrm` → **영희 / Younghee**
- `AvatarSample_C.vrm` → **철수 / Cheolsu**

Export or download the official VRoid Studio sample models and place the VRM files in this directory with those exact names before building the Android client.

The application does not fetch VRM assets from the network at runtime. If an asset is absent or invalid, the client falls back to the built-in DOM character instead of weakening the network/privacy boundary.

## License note

AvatarSample A–Z are not CC0. pixiv/VRoid retains copyright. The official VRoid sample-model terms permit broad use including commercial use, modification, redistribution, and use without mandatory attribution, subject to the current model conditions. Re-check the official VRoid sample-model terms before redistributing a release that bundles these files.

Official model names and terms must remain distinguishable from HearthGhost's fictional character names: `영희` and `철수` are HearthGhost presentation/persona labels, not official VRoid model names.
