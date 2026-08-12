import type { HearthGhostCharacterId } from "../character/catalog.js";
import type { CharacterDisplayProfile } from "../character/profile.js";
import type { CharacterPreferenceStorage } from "../character/preferences.js";

export type PersonaHumor = "low" | "moderate" | "high";
export type PersonaVerbosity = "concise" | "normal" | "detailed";
export type PersonaFormality = "casual" | "neutral" | "formal";
export type PersonaInitiative = "low" | "moderate" | "high";

export interface PersonaProfilePreset {
  readonly id: string;
  readonly name: string;
  readonly humor: PersonaHumor;
  readonly verbosity: PersonaVerbosity;
  readonly formality: PersonaFormality;
  readonly initiative: PersonaInitiative;
  readonly builtIn: boolean;
}

const PROFILE_STORAGE_KEY = "hearthghost.persona.profiles.v1";
const ACTIVE_PROFILE_STORAGE_KEY = "hearthghost.persona.active.v1";
const CUSTOM_ID = /^custom-[a-z0-9-]{8,80}$/;
const HUMOR = ["low", "moderate", "high"] as const;
const VERBOSITY = ["concise", "normal", "detailed"] as const;
const FORMALITY = ["casual", "neutral", "formal"] as const;
const INITIATIVE = ["low", "moderate", "high"] as const;
const MAX_CUSTOM_PROFILES = 12;
export const SERVER_ACTIVE_PERSONA_ID = "custom-server-active";

export const BUILT_IN_PERSONA_PROFILES: readonly PersonaProfilePreset[] = Object.freeze([
  Object.freeze({
    id: "younghee",
    name: "영희",
    humor: "moderate",
    verbosity: "normal",
    formality: "casual",
    initiative: "low",
    builtIn: true,
  }),
  Object.freeze({
    id: "cheolsu",
    name: "철수",
    humor: "low",
    verbosity: "concise",
    formality: "casual",
    initiative: "low",
    builtIn: true,
  }),
]);

export function loadPersonaProfiles(
  storage: CharacterPreferenceStorage | null,
): readonly PersonaProfilePreset[] {
  const custom: PersonaProfilePreset[] = [];
  try {
    const decoded = storage === null ? null : JSON.parse(storage.getItem(PROFILE_STORAGE_KEY) ?? "null");
    if (Array.isArray(decoded)) {
      for (const value of decoded.slice(0, MAX_CUSTOM_PROFILES)) {
        const profile = parseCustomProfile(value);
        if (profile !== null && !custom.some((candidate) => candidate.id === profile.id)) {
          custom.push(profile);
        }
      }
    }
  } catch {
    // Corrupt or unavailable local storage fails closed to reviewed built-ins.
  }
  return Object.freeze([...BUILT_IN_PERSONA_PROFILES, ...custom]);
}

export function loadActivePersonaId(
  storage: CharacterPreferenceStorage | null,
  profiles: readonly PersonaProfilePreset[],
  fallbackAppearance: HearthGhostCharacterId,
): string {
  try {
    const stored = storage?.getItem(ACTIVE_PROFILE_STORAGE_KEY) ?? "";
    if (profiles.some((profile) => profile.id === stored)) {
      return stored;
    }
  } catch {
    // Fall through to the appearance-matched built-in.
  }
  return fallbackAppearance;
}

export function saveActivePersonaId(
  storage: CharacterPreferenceStorage | null,
  profiles: readonly PersonaProfilePreset[],
  id: string,
): boolean {
  if (storage === null || !profiles.some((profile) => profile.id === id)) {
    return false;
  }
  try {
    storage.setItem(ACTIVE_PROFILE_STORAGE_KEY, id);
    return true;
  } catch {
    return false;
  }
}

export function saveCustomPersonaProfile(
  storage: CharacterPreferenceStorage | null,
  profiles: readonly PersonaProfilePreset[],
  profile: PersonaProfilePreset,
): readonly PersonaProfilePreset[] {
  const valid = parseCustomProfile(profile);
  if (storage === null || valid === null) {
    throw new Error("Custom persona profile is invalid or local storage is unavailable");
  }
  const custom = profiles.filter((candidate) => !candidate.builtIn && candidate.id !== valid.id);
  if (custom.length >= MAX_CUSTOM_PROFILES) {
    throw new Error("At most 12 custom persona profiles may be stored on this device");
  }
  const next = [...BUILT_IN_PERSONA_PROFILES, ...custom, valid];
  storage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(next.filter((candidate) => !candidate.builtIn)));
  return Object.freeze(next);
}

export function deleteCustomPersonaProfile(
  storage: CharacterPreferenceStorage | null,
  profiles: readonly PersonaProfilePreset[],
  id: string,
): readonly PersonaProfilePreset[] {
  if (storage === null || !CUSTOM_ID.test(id)) {
    return profiles;
  }
  const custom = profiles.filter((candidate) => !candidate.builtIn && candidate.id !== id);
  storage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(custom));
  return Object.freeze([...BUILT_IN_PERSONA_PROFILES, ...custom]);
}

export function personaProfileCommand(profile: PersonaProfilePreset): string {
  const validated = validateProfile(profile);
  return `페르소나:v1:${JSON.stringify({
    name: validated.name,
    humor: validated.humor,
    verbosity: validated.verbosity,
    formality: validated.formality,
    initiative: validated.initiative,
  })}`;
}

export function newCustomPersonaId(): string {
  return `custom-${crypto.randomUUID().toLowerCase()}`;
}

export function createCustomPersonaProfile(
  id: string,
  fields: Omit<PersonaProfilePreset, "id" | "builtIn">,
): PersonaProfilePreset {
  return Object.freeze(validateProfile({ id, ...fields, builtIn: false }));
}

export function findMatchingPersonaProfile(
  profiles: readonly PersonaProfilePreset[],
  serverProfile: CharacterDisplayProfile,
): PersonaProfilePreset | null {
  return profiles.find((profile) =>
    profile.name === serverProfile.name
    && profile.humor === serverProfile.humor
    && profile.verbosity === serverProfile.verbosity
    && profile.formality === serverProfile.formality
    && profile.initiative === serverProfile.initiative
  ) ?? null;
}

export function personaProfileFromServer(
  serverProfile: CharacterDisplayProfile,
): PersonaProfilePreset {
  return createCustomPersonaProfile(SERVER_ACTIVE_PERSONA_ID, serverProfile);
}

function parseCustomProfile(value: unknown): PersonaProfilePreset | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  const profile = value as Record<string, unknown>;
  if (
    Object.keys(profile).sort().join(",") !== "builtIn,formality,humor,id,initiative,name,verbosity"
    || profile.builtIn !== false
    || typeof profile.id !== "string"
    || !CUSTOM_ID.test(profile.id)
  ) {
    return null;
  }
  try {
    return Object.freeze(validateProfile(profile as unknown as PersonaProfilePreset));
  } catch {
    return null;
  }
}

function validateProfile(profile: PersonaProfilePreset): PersonaProfilePreset {
  if (
    typeof profile.name !== "string"
    || profile.name.trim() !== profile.name
    || profile.name.length < 1
    || profile.name.length > 80
    || /[\u0000-\u001f\u007f]/u.test(profile.name)
    || !HUMOR.includes(profile.humor)
    || !VERBOSITY.includes(profile.verbosity)
    || !FORMALITY.includes(profile.formality)
    || !INITIATIVE.includes(profile.initiative)
  ) {
    throw new Error("Persona fields are invalid");
  }
  return profile;
}
