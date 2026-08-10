import { Application, Assets, Sprite } from "pixi.js";

import type { CharacterRenderer } from "./renderer-contract";

export const pixiCandidate = {
  rendererContract: null as CharacterRenderer | null,
  runtimeSymbols: { Application, Assets, Sprite },
};
