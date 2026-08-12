import type { HearthGhostCharacterId } from "./catalog.js";
import type { CharacterEmotion, CharacterState } from "./semantic.js";

export type EmotionPostureRotation = readonly [number, number, number];

type EmotionPostureBoneName =
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

export interface VrmEmotionPostureFrame
  extends Readonly<Record<EmotionPostureBoneName, EmotionPostureRotation>> {}

interface EmotionPostureProfile {
  readonly scale: number;
  readonly lateralSign: -1 | 1;
  readonly expressiveness: number;
}

const BONES: readonly EmotionPostureBoneName[] = Object.freeze([
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

const PROFILES: Readonly<Record<HearthGhostCharacterId, EmotionPostureProfile>> = Object.freeze({
  younghee: Object.freeze({ scale: 1.0, lateralSign: 1, expressiveness: 1.0 }),
  cheolsu: Object.freeze({ scale: 0.76, lateralSign: -1, expressiveness: 0.72 }),
});

const GENERIC_PROFILE: EmotionPostureProfile = Object.freeze({
  scale: 0.82,
  lateralSign: 1,
  expressiveness: 0.78,
});

function zeroFrame(): Record<EmotionPostureBoneName, [number, number, number]> {
  return Object.fromEntries(BONES.map((bone) => [bone, [0, 0, 0]])) as Record<
    EmotionPostureBoneName,
    [number, number, number]
  >;
}

function approach(current: number, target: number, response: number, delta: number): number {
  const blend = 1 - Math.exp(-response * Math.max(0, Math.min(delta, 0.1)));
  return current + (target - current) * blend;
}

function stateInfluence(state: CharacterState): number {
  switch (state) {
    case "sleeping":
      return 0;
    case "noticing":
      return 1.0;
    case "listening":
      return 0.86;
    case "thinking":
      return 0.72;
    case "speaking":
      return 0.90;
    case "engaged":
      return 0.68;
  }
}

function emotionTarget(
  emotion: CharacterEmotion,
  profile: EmotionPostureProfile,
): Readonly<Partial<Record<EmotionPostureBoneName, EmotionPostureRotation>>> {
  const side = profile.lateralSign * profile.expressiveness;
  switch (emotion) {
    case "neutral":
      return Object.freeze({});
    case "happy":
      return Object.freeze({
        spine: [-0.004, 0, 0],
        chest: [-0.010, 0, 0.010],
        neck: [-0.004, 0, 0],
        head: [-0.008, 0, 0.004 * side],
        leftShoulder: [0, 0, -0.014],
        rightShoulder: [0, 0, 0.014],
        leftUpperArm: [0.010, 0, 0.008],
        rightUpperArm: [-0.010, 0, -0.008],
      });
    case "amused":
      return Object.freeze({
        spine: [-0.003, 0.006 * side, -0.004 * side],
        chest: [-0.008, 0.012 * side, 0.012 * side],
        neck: [-0.003, -0.008 * side, 0.014 * side],
        head: [-0.006, -0.014 * side, 0.028 * side],
        leftShoulder: [0, 0, -0.010 - 0.004 * side],
        rightShoulder: [0, 0, 0.010 - 0.004 * side],
        leftLowerArm: [-0.020, 0, 0.006 * side],
        rightLowerArm: [-0.018, 0, 0.006 * side],
      });
    case "curious":
      return Object.freeze({
        spine: [-0.008, 0, -0.004 * side],
        chest: [-0.014, 0.010 * side, -0.006 * side],
        neck: [-0.006, -0.008 * side, 0.018 * side],
        head: [-0.010, -0.016 * side, 0.034 * side],
        leftShoulder: [0, 0, -0.008],
        rightShoulder: [0, 0, 0.008],
      });
    case "concerned":
      return Object.freeze({
        spine: [0.006, 0, 0.003 * side],
        chest: [0.012, -0.006 * side, -0.004 * side],
        neck: [0.010, 0.004 * side, -0.006 * side],
        head: [0.018, 0.008 * side, -0.010 * side],
        leftShoulder: [0, 0, 0.012],
        rightShoulder: [0, 0, -0.012],
        leftUpperArm: [0.006, -0.008, -0.010],
        rightUpperArm: [-0.006, 0.008, 0.010],
        leftLowerArm: [-0.024, 0, 0],
        rightLowerArm: [-0.024, 0, 0],
      });
    case "surprised":
      return Object.freeze({
        spine: [0.010, 0, 0],
        chest: [0.018, 0, 0],
        neck: [-0.010, 0, 0],
        head: [-0.022, 0, 0],
        leftShoulder: [-0.008, 0, -0.022],
        rightShoulder: [-0.008, 0, 0.022],
        leftUpperArm: [0.020, -0.010, 0.014],
        rightUpperArm: [-0.020, 0.010, -0.014],
        leftLowerArm: [-0.020, 0, 0],
        rightLowerArm: [-0.020, 0, 0],
      });
    case "angry":
      return Object.freeze({
        spine: [-0.002, 0, 0],
        chest: [-0.006, 0, -0.002 * side],
        neck: [0.004, 0, 0],
        head: [0.006, 0.008 * side, -0.004 * side],
        leftShoulder: [-0.006, 0, 0.012],
        rightShoulder: [-0.006, 0, -0.012],
        leftUpperArm: [0.004, -0.010, -0.014],
        rightUpperArm: [-0.004, 0.010, 0.014],
        leftLowerArm: [-0.018, 0, 0],
        rightLowerArm: [-0.018, 0, 0],
      });
    case "sad":
      return Object.freeze({
        spine: [0.009, 0, 0],
        chest: [0.013, 0, 0],
        neck: [0.012, 0, 0],
        head: [0.022, 0.004 * side, -0.006 * side],
        leftShoulder: [0.003, 0, 0.010],
        rightShoulder: [0.003, 0, -0.010],
        leftUpperArm: [0.004, -0.005, -0.008],
        rightUpperArm: [-0.004, 0.005, 0.008],
      });
    case "annoyed":
      return Object.freeze({
        spine: [0.002, 0.006 * side, 0],
        chest: [0.004, 0.012 * side, -0.004 * side],
        neck: [0.002, -0.006 * side, -0.006 * side],
        head: [0.006, -0.018 * side, -0.014 * side],
        leftShoulder: [-0.004, 0, 0.006],
        rightShoulder: [-0.004, 0, -0.006],
      });
    case "embarrassed":
      return Object.freeze({
        spine: [0.006, -0.004 * side, 0.004 * side],
        chest: [0.010, -0.008 * side, 0.004 * side],
        neck: [0.010, 0.010 * side, -0.010 * side],
        head: [0.018, 0.020 * side, -0.022 * side],
        leftShoulder: [0.002, 0, 0.010],
        rightShoulder: [0.002, 0, -0.010],
        leftUpperArm: [0.004, -0.008, -0.008],
        rightUpperArm: [-0.004, 0.008, 0.008],
        leftLowerArm: [-0.016, 0, 0],
        rightLowerArm: [-0.016, 0, 0],
      });
    case "smug":
      return Object.freeze({
        spine: [-0.003, 0.008 * side, -0.003 * side],
        chest: [-0.006, 0.014 * side, 0.008 * side],
        neck: [-0.002, -0.010 * side, 0.010 * side],
        head: [-0.004, -0.018 * side, 0.022 * side],
        leftShoulder: [0, 0, -0.008],
        rightShoulder: [0, 0, 0.008],
      });
    case "affectionate":
      return Object.freeze({
        spine: [-0.005, 0, -0.002 * side],
        chest: [-0.010, 0.006 * side, 0.006 * side],
        neck: [-0.004, -0.006 * side, 0.010 * side],
        head: [-0.008, -0.010 * side, 0.018 * side],
        leftShoulder: [0, 0, -0.010],
        rightShoulder: [0, 0, 0.010],
      });
  }
}

/**
 * Low-amplitude body-language overlay for semantic emotion.
 *
 * The face remains the primary emotion channel. This layer only nudges the
 * silhouette so the same state/posture reads differently when the character
 * is curious, concerned, amused, and so on. It never translates the root and
 * runs below semantic gestures, so an explicit gesture always wins.
 */
export class EmotionPostureController {
  private readonly profile: EmotionPostureProfile;
  private readonly current = zeroFrame();
  private readonly target = zeroFrame();
  private lastEmotion: CharacterEmotion = "neutral";
  private lastState: CharacterState = "sleeping";

  constructor(characterId: HearthGhostCharacterId | null = null) {
    this.profile = characterId === null ? GENERIC_PROFILE : PROFILES[characterId];
  }

  reset(): void {
    this.lastEmotion = "neutral";
    this.lastState = "sleeping";
    for (const bone of BONES) {
      this.current[bone] = [0, 0, 0];
      this.target[bone] = [0, 0, 0];
    }
  }

  update(
    delta: number,
    state: CharacterState,
    emotion: CharacterEmotion,
  ): VrmEmotionPostureFrame {
    if (emotion !== this.lastEmotion || state !== this.lastState) {
      this.selectTarget(state, emotion);
      this.lastEmotion = emotion;
      this.lastState = state;
    }

    const response = emotion === "surprised" && state === "noticing" ? 6.2 : 3.5;
    for (const bone of BONES) {
      const current = this.current[bone];
      const target = this.target[bone];
      current[0] = approach(current[0], target[0], response, delta);
      current[1] = approach(current[1], target[1], response, delta);
      current[2] = approach(current[2], target[2], response, delta);
    }
    return this.current;
  }

  private selectTarget(state: CharacterState, emotion: CharacterEmotion): void {
    for (const bone of BONES) {
      this.target[bone] = [0, 0, 0];
    }
    const influence = stateInfluence(state) * this.profile.scale;
    if (influence === 0 || emotion === "neutral") {
      return;
    }
    const target = emotionTarget(emotion, this.profile);
    for (const [bone, rotation] of Object.entries(target) as [
      EmotionPostureBoneName,
      EmotionPostureRotation,
    ][]) {
      this.target[bone] = [
        rotation[0] * influence,
        rotation[1] * influence,
        rotation[2] * influence,
      ];
    }
  }
}
