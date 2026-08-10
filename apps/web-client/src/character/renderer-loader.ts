import { DomCharacterRenderer } from "./dom-renderer.js";
import type { CharacterRenderer } from "./renderer.js";

export type CharacterRendererKind = "dom" | "vrm";

export async function loadCharacterRenderer(
  kind: CharacterRendererKind,
): Promise<CharacterRenderer> {
  if (kind === "vrm") {
    const { createVrmCharacterRenderer } = await import("./vrm-renderer.js");
    return createVrmCharacterRenderer();
  }
  return new DomCharacterRenderer();
}
