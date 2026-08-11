export interface CharacterDisplayProfile {
  readonly name: string;
}

export function parseCharacterDisplayProfile(value: unknown): CharacterDisplayProfile {
  if (
    typeof value !== "object"
    || value === null
    || Array.isArray(value)
    || Object.keys(value).length !== 1
    || !("name" in value)
  ) {
    throw new Error("Character display profile must contain exactly name");
  }
  const name = value.name;
  if (
    typeof name !== "string"
    || name.length === 0
    || name !== name.trim()
    || [...name].length > 80
    || [...name].some((character) => /\p{C}/u.test(character))
  ) {
    throw new Error("Character display name is invalid");
  }
  return Object.freeze({ name });
}
