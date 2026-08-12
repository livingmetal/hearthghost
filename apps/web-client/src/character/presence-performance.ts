import type { HearthGhostCharacterId } from "./catalog.js";
import type { CharacterGesture } from "./semantic.js";

export type PresenceMotionPhase = "enter" | "exit";

export interface PresenceMotionKeyframe {
  readonly opacity: number;
  readonly transform: string;
  readonly offset?: number;
}

export interface PresenceMotionVariant {
  readonly id: string;
  readonly durationMillis: number;
  readonly easing: string;
  readonly keyframes: readonly PresenceMotionKeyframe[];
}

const YOUNGHEE_ENTRANCES: readonly PresenceMotionVariant[] = Object.freeze([
  Object.freeze({
    id: "younghee.enter.peek-left",
    durationMillis: 830,
    easing: "cubic-bezier(0.18, 0.78, 0.22, 1)",
    keyframes: Object.freeze([
      Object.freeze({ opacity: 0, transform: "translate3d(-72%, 10%, 0) scale(0.94)", offset: 0 }),
      Object.freeze({ opacity: 0.92, transform: "translate3d(-43%, 5%, 0) scale(0.98)", offset: 0.30 }),
      Object.freeze({ opacity: 1, transform: "translate3d(-38%, 4%, 0) scale(0.985)", offset: 0.48 }),
      Object.freeze({ opacity: 1, transform: "translate3d(0, 0, 0) scale(1)", offset: 1 }),
    ]),
  }),
  Object.freeze({
    id: "younghee.enter.soft-left",
    durationMillis: 820,
    easing: "cubic-bezier(0.22, 0.72, 0.22, 1)",
    keyframes: Object.freeze([
      Object.freeze({ opacity: 0, transform: "translate3d(-52%, 8%, 0) scale(0.97)", offset: 0 }),
      Object.freeze({ opacity: 1, transform: "translate3d(-10%, 1%, 0) scale(0.995)", offset: 0.72 }),
      Object.freeze({ opacity: 1, transform: "translate3d(0, 0, 0) scale(1)", offset: 1 }),
    ]),
  }),
]);

const YOUNGHEE_EXITS: readonly PresenceMotionVariant[] = Object.freeze([
  Object.freeze({
    id: "younghee.exit.wave-left",
    durationMillis: 650,
    easing: "cubic-bezier(0.38, 0, 0.72, 0.28)",
    keyframes: Object.freeze([
      Object.freeze({ opacity: 1, transform: "translate3d(0, 0, 0) scale(1)", offset: 0 }),
      Object.freeze({ opacity: 0.96, transform: "translate3d(-7%, 1%, 0) scale(0.998)", offset: 0.34 }),
      Object.freeze({ opacity: 0, transform: "translate3d(-54%, 9%, 0) scale(0.97)", offset: 1 }),
    ]),
  }),
  Object.freeze({
    id: "younghee.exit.quick-left",
    durationMillis: 620,
    easing: "cubic-bezier(0.4, 0, 0.7, 0.3)",
    keyframes: Object.freeze([
      Object.freeze({ opacity: 1, transform: "translate3d(0, 0, 0) scale(1)", offset: 0 }),
      Object.freeze({ opacity: 0.82, transform: "translate3d(-16%, 2%, 0) scale(0.992)", offset: 0.50 }),
      Object.freeze({ opacity: 0, transform: "translate3d(-50%, 8%, 0) scale(0.975)", offset: 1 }),
    ]),
  }),
]);

const CHEOLSU_ENTRANCES: readonly PresenceMotionVariant[] = Object.freeze([
  Object.freeze({
    id: "cheolsu.enter.measured-right",
    durationMillis: 760,
    easing: "cubic-bezier(0.24, 0.66, 0.24, 1)",
    keyframes: Object.freeze([
      Object.freeze({ opacity: 0, transform: "translate3d(44%, 4%, 0) scale(0.99)", offset: 0 }),
      Object.freeze({ opacity: 1, transform: "translate3d(8%, 0.5%, 0) scale(0.998)", offset: 0.74 }),
      Object.freeze({ opacity: 1, transform: "translate3d(0, 0, 0) scale(1)", offset: 1 }),
    ]),
  }),
  Object.freeze({
    id: "cheolsu.enter.short-step",
    durationMillis: 820,
    easing: "cubic-bezier(0.22, 0.7, 0.24, 1)",
    keyframes: Object.freeze([
      Object.freeze({ opacity: 0, transform: "translate3d(34%, 2%, 0) scale(0.988)", offset: 0 }),
      Object.freeze({ opacity: 0.94, transform: "translate3d(14%, 0.7%, 0) scale(0.995)", offset: 0.54 }),
      Object.freeze({ opacity: 1, transform: "translate3d(0, 0, 0) scale(1)", offset: 1 }),
    ]),
  }),
]);

const CHEOLSU_EXITS: readonly PresenceMotionVariant[] = Object.freeze([
  Object.freeze({
    id: "cheolsu.exit.measured-right",
    durationMillis: 650,
    easing: "cubic-bezier(0.38, 0, 0.72, 0.3)",
    keyframes: Object.freeze([
      Object.freeze({ opacity: 1, transform: "translate3d(0, 0, 0) scale(1)", offset: 0 }),
      Object.freeze({ opacity: 0.96, transform: "translate3d(6%, 0, 0) scale(0.998)", offset: 0.34 }),
      Object.freeze({ opacity: 0, transform: "translate3d(46%, 4%, 0) scale(0.99)", offset: 1 }),
    ]),
  }),
  Object.freeze({
    id: "cheolsu.exit.quiet-right",
    durationMillis: 620,
    easing: "cubic-bezier(0.4, 0, 0.7, 0.3)",
    keyframes: Object.freeze([
      Object.freeze({ opacity: 1, transform: "translate3d(0, 0, 0) scale(1)", offset: 0 }),
      Object.freeze({ opacity: 0.85, transform: "translate3d(15%, 1%, 0) scale(0.996)", offset: 0.52 }),
      Object.freeze({ opacity: 0, transform: "translate3d(43%, 4%, 0) scale(0.99)", offset: 1 }),
    ]),
  }),
]);

const GENERIC_ENTER: PresenceMotionVariant = Object.freeze({
  id: "generic.enter.side",
  durationMillis: 850,
  easing: "cubic-bezier(0.22, 0.72, 0.22, 1)",
  keyframes: Object.freeze([
    Object.freeze({ opacity: 0, transform: "translate3d(-42%, 5%, 0) scale(0.985)", offset: 0 }),
    Object.freeze({ opacity: 1, transform: "translate3d(0, 0, 0) scale(1)", offset: 1 }),
  ]),
});

const GENERIC_EXIT: PresenceMotionVariant = Object.freeze({
  id: "generic.exit.side",
  durationMillis: 650,
  easing: "cubic-bezier(0.4, 0, 0.7, 0.3)",
  keyframes: Object.freeze([
    Object.freeze({ opacity: 1, transform: "translate3d(0, 0, 0) scale(1)", offset: 0 }),
    Object.freeze({ opacity: 0, transform: "translate3d(-46%, 7%, 0) scale(0.985)", offset: 1 }),
  ]),
});

export function characterIdFromViewportLabel(label: string): HearthGhostCharacterId | null {
  if (label.startsWith("영희")) return "younghee";
  if (label.startsWith("철수")) return "cheolsu";
  return null;
}

export function presenceMotionFor(
  characterId: HearthGhostCharacterId | null,
  phase: PresenceMotionPhase,
  cycle: number,
): PresenceMotionVariant {
  const index = Math.max(0, Math.trunc(cycle));
  if (characterId === "younghee") {
    const variants = phase === "enter" ? YOUNGHEE_ENTRANCES : YOUNGHEE_EXITS;
    return variants[index % variants.length] ?? variants[0] ?? (phase === "enter" ? GENERIC_ENTER : GENERIC_EXIT);
  }
  if (characterId === "cheolsu") {
    const variants = phase === "enter" ? CHEOLSU_ENTRANCES : CHEOLSU_EXITS;
    return variants[index % variants.length] ?? variants[0] ?? (phase === "enter" ? GENERIC_ENTER : GENERIC_EXIT);
  }
  return phase === "enter" ? GENERIC_ENTER : GENERIC_EXIT;
}

export function exitPreludeGestureFor(
  characterId: HearthGhostCharacterId | null,
  cycle: number,
): CharacterGesture | null {
  const even = Math.abs(Math.trunc(cycle)) % 2 === 0;
  if (characterId === "younghee") {
    return even ? Object.freeze({ gesture: "wave", side: "right" }) : Object.freeze({ gesture: "nod" });
  }
  if (characterId === "cheolsu") {
    return even ? Object.freeze({ gesture: "nod" }) : null;
  }
  return null;
}
