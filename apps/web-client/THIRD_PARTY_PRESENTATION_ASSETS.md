# Third-party presentation assets

## AIRI `idle_loop.vrma`

HearthGhost uses one pinned VRM Animation asset from AIRI as an optional local
base idle animation.

- Repository: `moeru-ai/airi`
- Commit: `b6011381bc34a6b85ad669363513cb1a2eea6438`
- Source path: `packages/stage-ui-three/src/assets/vrm/animations/idle_loop.vrma`
- Git blob: `26b28f4e4227c48eecdd29d25e3dc6f4c6ac3844`
- Local runtime path: `/animations/airi-idle-loop.vrma`
- License: MIT

The asset is fetched only during the reviewed build/development asset step and
its Git blob identity is verified before it enters the local Vite/Android asset
tree. HearthGhost does not fetch this asset from AIRI at application runtime.
Only humanoid base-animation tracks are admitted to the HearthGhost animation
mixer; expression and look-at animation remain controlled by HearthGhost.
Hips translation is re-anchored to the active VRM and bounded to a small idle
envelope so the idle clip cannot move the avatar across the stage.

MIT License

Copyright (c) 2024-PRESENT Neko Ayaka

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
