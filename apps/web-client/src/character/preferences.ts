import {
  characterById,
  type HearthGhostCharacterId,
} from "./catalog.js";

export const DEFAULT_CHARACTER_ID: HearthGhostCharacterId = "younghee";
export const CHARACTER_PREFERENCE_STORAGE_KEY = "hearthghost.character.v1";

export interface CharacterPreferenceStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export function browserCharacterPreferenceStorage(): CharacterPreferenceStorage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function loadPreferredCharacterId(
  storage: CharacterPreferenceStorage | null,
): HearthGhostCharacterId {
  if (storage === null) {
    return DEFAULT_CHARACTER_ID;
  }
  try {
    const stored = storage.getItem(CHARACTER_PREFERENCE_STORAGE_KEY);
    return characterById(stored ?? "")?.id ?? DEFAULT_CHARACTER_ID;
  } catch {
    return DEFAULT_CHARACTER_ID;
  }
}

export function savePreferredCharacterId(
  storage: CharacterPreferenceStorage | null,
  id: HearthGhostCharacterId,
): boolean {
  if (characterById(id) === null || storage === null) {
    return false;
  }
  try {
    storage.setItem(CHARACTER_PREFERENCE_STORAGE_KEY, id);
    return true;
  } catch {
    return false;
  }
}
