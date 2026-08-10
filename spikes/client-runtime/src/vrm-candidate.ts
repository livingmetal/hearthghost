import { PerspectiveCamera, Scene, WebGLRenderer } from "three";
import { VRMLoaderPlugin } from "@pixiv/three-vrm";

import type { CharacterRenderer } from "./renderer-contract";

export const vrmCandidate = {
  rendererContract: null as CharacterRenderer | null,
  runtimeSymbols: { PerspectiveCamera, Scene, WebGLRenderer, VRMLoaderPlugin },
};
