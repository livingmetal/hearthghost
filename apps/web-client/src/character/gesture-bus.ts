import {
  parseCharacterSemanticEvent,
  type CharacterGesture,
} from "./semantic.js";

export type CharacterGestureListener = (gesture: CharacterGesture) => void;

const listeners = new Set<CharacterGestureListener>();

export function publishCharacterGesture(gesture: CharacterGesture): void {
  const event = parseCharacterSemanticEvent({
    type: "character.gesture",
    payload: gesture,
  });
  if (event.type !== "character.gesture") {
    return;
  }
  for (const listener of listeners) {
    listener(event.payload);
  }
}

export function subscribeCharacterGestures(
  listener: CharacterGestureListener,
): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
