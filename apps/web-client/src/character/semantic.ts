export const CHARACTER_STATES = [
  "sleeping",
  "listening",
  "thinking",
  "speaking",
  "engaged",
] as const;

export const CHARACTER_EMOTIONS = [
  "neutral",
  "happy",
  "amused",
  "curious",
  "concerned",
  "surprised",
] as const;

export type CharacterState = (typeof CHARACTER_STATES)[number];
export type CharacterEmotion = (typeof CHARACTER_EMOTIONS)[number];

export interface CharacterPresentation {
  readonly state: CharacterState;
  readonly emotion: CharacterEmotion;
}

export type CharacterSemanticEvent =
  | Readonly<{ type: "character.state"; payload: Readonly<{ state: CharacterState }> }>
  | Readonly<{ type: "character.emotion"; payload: Readonly<{ emotion: CharacterEmotion }> }>;

export const INITIAL_PRESENTATION: CharacterPresentation = Object.freeze({
  state: "sleeping",
  emotion: "neutral",
});

function isExactObject(value: unknown, field: string): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    Object.keys(value).length === 1 &&
    Object.hasOwn(value, field)
  );
}

export function parseCharacterSemanticEvent(value: unknown): CharacterSemanticEvent {
  if (
    typeof value !== "object" ||
    value === null ||
    Array.isArray(value) ||
    Object.keys(value).length !== 2 ||
    !("type" in value) ||
    !("payload" in value)
  ) {
    throw new Error("Character event must contain exactly type and payload");
  }

  if (value.type === "character.state" && isExactObject(value.payload, "state")) {
    if (CHARACTER_STATES.includes(value.payload.state as CharacterState)) {
      return value as CharacterSemanticEvent;
    }
    throw new Error("Unknown semantic character state");
  }

  if (value.type === "character.emotion" && isExactObject(value.payload, "emotion")) {
    if (CHARACTER_EMOTIONS.includes(value.payload.emotion as CharacterEmotion)) {
      return value as CharacterSemanticEvent;
    }
    throw new Error("Unknown semantic character emotion");
  }

  throw new Error("Unknown or malformed semantic character event");
}

export function reduceCharacterPresentation(
  current: CharacterPresentation,
  event: CharacterSemanticEvent,
): CharacterPresentation {
  if (event.type === "character.state") {
    return Object.freeze({ ...current, state: event.payload.state });
  }
  return Object.freeze({ ...current, emotion: event.payload.emotion });
}
