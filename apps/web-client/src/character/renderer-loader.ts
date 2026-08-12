import { CHARACTER_CATALOG } from "./catalog.js";
import { DomCharacterRenderer } from "./dom-renderer.js";
import type { CharacterRenderer } from "./renderer.js";

export type CharacterRendererKind = "dom" | "vrm";

export async function loadCharacterRenderer(
  kind: CharacterRendererKind,
  assetUrl: string | null = null,
): Promise<CharacterRenderer> {
  if (kind === "vrm") {
    const { createVrmCharacterRenderer } = await import("./vrm-renderer.js");
    const characterId = assetUrl === null
      ? null
      : CHARACTER_CATALOG.find((candidate) => candidate.assetUrl === assetUrl)?.id ?? null;
    return createVrmCharacterRenderer(assetUrl, characterId);
  }
  return new DomCharacterRenderer();
}
