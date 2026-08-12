export interface CharacterDisplayProfile {
  readonly name: string;
  readonly humor: "low" | "moderate" | "high";
  readonly verbosity: "concise" | "normal" | "detailed";
  readonly formality: "casual" | "neutral" | "formal";
  readonly initiative: "low" | "moderate" | "high";
}

export function parseCharacterDisplayProfile(value: unknown): CharacterDisplayProfile {
  if (
    typeof value !== "object"
    || value === null
    || Array.isArray(value)
    || Object.keys(value).sort().join(",") !== "formality,humor,initiative,name,verbosity"
  ) {
    throw new Error("Character display profile must contain exactly the typed persona fields");
  }
  const document = value as Record<string, unknown>;
  const name = document.name;
  if (
    typeof name !== "string"
    || name.length === 0
    || name !== name.trim()
    || [...name].length > 80
    || [...name].some((character) => /\p{C}/u.test(character))
  ) {
    throw new Error("Character display name is invalid");
  }
  if (
    !isChoice(document.humor, ["low", "moderate", "high"])
    || !isChoice(document.verbosity, ["concise", "normal", "detailed"])
    || !isChoice(document.formality, ["casual", "neutral", "formal"])
    || !isChoice(document.initiative, ["low", "moderate", "high"])
  ) {
    throw new Error("Character persona choices are invalid");
  }
  return Object.freeze({
    name,
    humor: document.humor,
    verbosity: document.verbosity,
    formality: document.formality,
    initiative: document.initiative,
  });
}

function isChoice<T extends string>(value: unknown, choices: readonly T[]): value is T {
  return typeof value === "string" && choices.includes(value as T);
}
