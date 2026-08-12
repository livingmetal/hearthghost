export type HearthGhostCharacterId = "younghee" | "cheolsu";

export interface CharacterVoiceProfile {
  readonly id: HearthGhostCharacterId;
  readonly pitch: number;
  readonly rate: number;
}

export interface HearthGhostCharacterDefinition {
  readonly id: HearthGhostCharacterId;
  readonly name: "영희" | "철수";
  readonly sample: "AvatarSample_Y" | "AvatarSample_C";
  readonly assetUrl: string;
  readonly voice: CharacterVoiceProfile;
}

export const CHARACTER_CATALOG: readonly HearthGhostCharacterDefinition[] = Object.freeze([
  Object.freeze({
    id: "younghee",
    name: "영희",
    sample: "AvatarSample_Y",
    assetUrl: "/models/AvatarSample_Y.vrm",
    voice: Object.freeze({ id: "younghee", pitch: 1.10, rate: 1.04 }),
  }),
  Object.freeze({
    id: "cheolsu",
    name: "철수",
    sample: "AvatarSample_C",
    assetUrl: "/models/AvatarSample_C.vrm",
    voice: Object.freeze({ id: "cheolsu", pitch: 0.88, rate: 0.94 }),
  }),
]);

export function characterByName(name: string): HearthGhostCharacterDefinition | null {
  return CHARACTER_CATALOG.find((candidate) => candidate.name === name) ?? null;
}

export function characterById(id: string): HearthGhostCharacterDefinition | null {
  return CHARACTER_CATALOG.find((candidate) => candidate.id === id) ?? null;
}

export function selectionCommand(character: HearthGhostCharacterDefinition): string {
  return `캐릭터: ${character.name}`;
}
