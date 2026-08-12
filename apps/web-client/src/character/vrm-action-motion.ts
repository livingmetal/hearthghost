import type { HearthGhostCharacterId } from "./catalog.js";
import type { CharacterGesture } from "./semantic.js";

export type ActionMotionBoneName =
  | "spine"
  | "chest"
  | "neck"
  | "head"
  | "leftShoulder"
  | "rightShoulder"
  | "leftUpperArm"
  | "rightUpperArm"
  | "leftLowerArm"
  | "rightLowerArm"
  | "leftHand"
  | "rightHand";

export type ActionMotionRotation = readonly [number, number, number];

export interface VrmActionMotionFrame {
  readonly rotations: Readonly<Record<ActionMotionBoneName, ActionMotionRotation>>;
  readonly leftHandOpen: number;
  readonly rightHandOpen: number;
}

export type SupportedActionGesture = Extract<
  CharacterGesture,
  { gesture: "clap" | "shrug" | "stretch" }
>;

const BONES: readonly ActionMotionBoneName[] = Object.freeze([
  "spine",
  "chest",
  "neck",
  "head",
  "leftShoulder",
  "rightShoulder",
  "leftUpperArm",
  "rightUpperArm",
  "leftLowerArm",
  "rightLowerArm",
  "leftHand",
  "rightHand",
]);

interface ActionProfile {
  readonly scale: number;
  readonly clapCycles: number;
  readonly tiltSign: -1 | 1;
}

const PROFILES: Readonly<Record<HearthGhostCharacterId, ActionProfile>> = Object.freeze({
  younghee: Object.freeze({ scale: 1.0, clapCycles: 3, tiltSign: 1 }),
  cheolsu: Object.freeze({ scale: 0.82, clapCycles: 2, tiltSign: -1 }),
});

const GENERIC_PROFILE: ActionProfile = Object.freeze({
  scale: 0.90,
  clapCycles: 2,
  tiltSign: 1,
});

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function ease(value: number): number {
  const t = clamp01(value);
  return (1 - Math.cos(Math.PI * t)) / 2;
}

function envelope(progress: number, rise: number, fall: number): number {
  const p = clamp01(progress);
  if (p < rise) {
    return ease(p / rise);
  }
  if (p > 1 - fall) {
    return ease((1 - p) / fall);
  }
  return 1;
}

function emptyRotations(): Record<ActionMotionBoneName, [number, number, number]> {
  return Object.fromEntries(BONES.map((bone) => [bone, [0, 0, 0]])) as Record<
    ActionMotionBoneName,
    [number, number, number]
  >;
}

function scaleRotation(
  rotation: ActionMotionRotation,
  scale: number,
): [number, number, number] {
  return [rotation[0] * scale, rotation[1] * scale, rotation[2] * scale];
}

function freezeFrame(
  rotations: Record<ActionMotionBoneName, [number, number, number]>,
  leftHandOpen: number,
  rightHandOpen: number,
): VrmActionMotionFrame {
  return Object.freeze({
    rotations: Object.freeze(rotations),
    leftHandOpen: clamp01(leftHandOpen),
    rightHandOpen: clamp01(rightHandOpen),
  });
}

function clapFrame(progress: number, profile: ActionProfile): VrmActionMotionFrame {
  const p = clamp01(progress);
  const amount = envelope(p, 0.16, 0.18) * profile.scale;
  const pulse = (1 - Math.cos(p * Math.PI * 2 * profile.clapCycles)) / 2;
  const close = pulse * amount;
  const rotations = emptyRotations();

  rotations.spine = scaleRotation([-0.018, 0, 0], amount);
  rotations.chest = scaleRotation([-0.035, 0, 0], amount);
  rotations.leftShoulder = scaleRotation([0, 0, -0.055], amount);
  rotations.rightShoulder = scaleRotation([0, 0, 0.055], amount);
  rotations.leftUpperArm = scaleRotation([-0.18, -0.10 - 0.08 * pulse, -0.34], amount);
  rotations.rightUpperArm = scaleRotation([-0.18, 0.10 + 0.08 * pulse, 0.34], amount);
  rotations.leftLowerArm = scaleRotation([-0.72, 0.16 + 0.14 * pulse, 0.05 + 0.08 * close], amount);
  rotations.rightLowerArm = scaleRotation([-0.72, -0.16 - 0.14 * pulse, -0.05 - 0.08 * close], amount);
  rotations.leftHand = scaleRotation([0.02, 0.20 + 0.16 * pulse, -0.04], amount);
  rotations.rightHand = scaleRotation([0.02, -0.20 - 0.16 * pulse, 0.04], amount);

  return freezeFrame(rotations, amount, amount);
}

function shrugFrame(progress: number, profile: ActionProfile): VrmActionMotionFrame {
  const amount = envelope(progress, 0.26, 0.28) * profile.scale;
  const tilt = profile.tiltSign * 0.020 * amount;
  const rotations = emptyRotations();

  rotations.spine = [0.010 * amount, 0, -tilt * 0.35];
  rotations.chest = [0.016 * amount, 0, tilt];
  rotations.neck = [0, 0, -tilt * 0.55];
  rotations.head = [0, 0, -tilt];
  rotations.leftShoulder = [-0.10 * amount, 0, -0.095 * amount];
  rotations.rightShoulder = [-0.10 * amount, 0, 0.095 * amount];
  rotations.leftUpperArm = [-0.035 * amount, -0.035 * amount, -0.12 * amount];
  rotations.rightUpperArm = [-0.035 * amount, 0.035 * amount, 0.12 * amount];
  rotations.leftLowerArm = [-0.24 * amount, -0.035 * amount, 0.035 * amount];
  rotations.rightLowerArm = [-0.24 * amount, 0.035 * amount, -0.035 * amount];
  rotations.leftHand = [0.02 * amount, -0.04 * amount, -0.08 * amount];
  rotations.rightHand = [0.02 * amount, 0.04 * amount, 0.08 * amount];

  return freezeFrame(rotations, amount, amount);
}

function stretchFrame(progress: number, profile: ActionProfile): VrmActionMotionFrame {
  const amount = envelope(progress, 0.30, 0.30) * profile.scale;
  const rotations = emptyRotations();

  rotations.spine = [-0.045 * amount, 0, 0];
  rotations.chest = [-0.090 * amount, 0, 0];
  rotations.neck = [-0.020 * amount, 0, 0];
  rotations.head = [-0.040 * amount, 0, 0];
  rotations.leftShoulder = [0, 0, -0.08 * amount];
  rotations.rightShoulder = [0, 0, 0.08 * amount];
  rotations.leftUpperArm = [-0.16 * amount, -0.08 * amount, -0.86 * amount];
  rotations.rightUpperArm = [-0.16 * amount, 0.08 * amount, 0.86 * amount];
  rotations.leftLowerArm = [-0.34 * amount, -0.06 * amount, 0.02 * amount];
  rotations.rightLowerArm = [-0.34 * amount, 0.06 * amount, -0.02 * amount];
  rotations.leftHand = [0.04 * amount, -0.02 * amount, -0.02 * amount];
  rotations.rightHand = [0.04 * amount, 0.02 * amount, 0.02 * amount];

  return freezeFrame(rotations, amount, amount);
}

export function actionMotionFrame(
  gesture: SupportedActionGesture,
  progress: number,
  characterId: HearthGhostCharacterId | null,
): VrmActionMotionFrame {
  const profile = characterId === null ? GENERIC_PROFILE : PROFILES[characterId];
  switch (gesture.gesture) {
    case "clap":
      return clapFrame(progress, profile);
    case "shrug":
      return shrugFrame(progress, profile);
    case "stretch":
      return stretchFrame(progress, profile);
  }
}
