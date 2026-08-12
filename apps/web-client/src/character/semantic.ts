export const CHARACTER_STATES = [
  "sleeping",
  "noticing",
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

export const CHARACTER_GESTURES = [
  "wave",
  "nod",
  "shake_head",
  "raise_hand",
  "turn",
  "bow",
] as const;

export const CHARACTER_SIDES = ["left", "right"] as const;

export type CharacterState = (typeof CHARACTER_STATES)[number];
export type CharacterEmotion = (typeof CHARACTER_EMOTIONS)[number];
export type CharacterGestureName = (typeof CHARACTER_GESTURES)[number];
export type CharacterSide = (typeof CHARACTER_SIDES)[number];

export type CharacterGesture =
  | Readonly<{ gesture: "wave"; side: CharacterSide }>
  | Readonly<{ gesture: "raise_hand"; side: CharacterSide }>
  | Readonly<{ gesture: "turn"; direction: CharacterSide }>
  | Readonly<{ gesture: "nod" }>
  | Readonly<{ gesture: "shake_head" }>
  | Readonly<{ gesture: "bow" }>;

export interface CharacterPresentation {
  readonly state: CharacterState;
  readonly emotion: CharacterEmotion;
}

export type CharacterSemanticEvent =
  | Readonly<{ type: "character.state"; payload: Readonly<{ state: CharacterState }> }>
  | Readonly<{ type: "character.emotion"; payload: Readonly<{ emotion: CharacterEmotion }> }>
  | Readonly<{ type: "character.gesture"; payload: CharacterGesture }>;

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

function parseGesturePayload(value: unknown): CharacterGesture {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("Character gesture payload must be an object");
  }
  const payload = value as Record<string, unknown>;
  const gesture = payload.gesture;
  if (!CHARACTER_GESTURES.includes(gesture as CharacterGestureName)) {
    throw new Error("Unknown semantic character gesture");
  }

  if (gesture === "wave" || gesture === "raise_hand") {
    if (
      Object.keys(payload).length !== 2
      || !CHARACTER_SIDES.includes(payload.side as CharacterSide)
    ) {
      throw new Error("Hand gesture requires exactly a left or right side");
    }
    return payload as CharacterGesture;
  }

  if (gesture === "turn") {
    if (
      Object.keys(payload).length !== 2
      || !CHARACTER_SIDES.includes(payload.direction as CharacterSide)
    ) {
      throw new Error("Turn gesture requires exactly a left or right direction");
    }
    return payload as CharacterGesture;
  }

  if (Object.keys(payload).length !== 1) {
    throw new Error("Body gesture contains unexpected parameters");
  }
  return payload as CharacterGesture;
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

  if (value.type === "character.gesture") {
    return Object.freeze({
      type: "character.gesture",
      payload: parseGesturePayload(value.payload),
    });
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
  if (event.type === "character.emotion") {
    return Object.freeze({ ...current, emotion: event.payload.emotion });
  }
  return current;
}
