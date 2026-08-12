import type { CharacterState } from "./semantic.js";

export type PostureRotation = readonly [number, number, number];

export interface VrmPostureFrame {
  readonly spine: PostureRotation;
  readonly chest: PostureRotation;
  readonly neck: PostureRotation;
  readonly head: PostureRotation;
  readonly leftShoulder: PostureRotation;
  readonly rightShoulder: PostureRotation;
  readonly leftUpperArm: PostureRotation;
  readonly rightUpperArm: PostureRotation;
  readonly leftLowerArm: PostureRotation;
  readonly rightLowerArm: PostureRotation;
  readonly leftHand: PostureRotation;
  readonly rightHand: PostureRotation;
}

interface PostureScalarState {
  lean: number;
  tilt: number;
  openness: number;
  elbow: number;
  headPitch: number;
  thinking: number;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, value));
}

function approach(current: number, target: number, response: number, delta: number): number {
  const blend = 1 - Math.exp(-response * Math.max(0, Math.min(delta, 0.1)));
  return current + (target - current) * blend;
}

function stateTarget(state: CharacterState): PostureScalarState {
  switch (state) {
    case "sleeping":
      return { lean: 0.022, tilt: 0, openness: -0.018, elbow: 0.04, headPitch: 0.045, thinking: 0 };
    case "thinking":
      return { lean: 0.018, tilt: 0.018, openness: -0.010, elbow: 0.08, headPitch: 0.025, thinking: 1 };
    case "listening":
      return { lean: -0.012, tilt: 0.010, openness: 0.010, elbow: 0.06, headPitch: -0.010, thinking: 0 };
    case "noticing":
      return { lean: -0.010, tilt: 0.004, openness: 0.025, elbow: 0.035, headPitch: -0.015, thinking: 0 };
    case "speaking":
      return { lean: -0.006, tilt: 0.008, openness: 0.018, elbow: 0.075, headPitch: -0.006, thinking: 0 };
    case "engaged":
      return { lean: 0, tilt: 0.008, openness: 0.008, elbow: 0.055, headPitch: 0, thinking: 0 };
  }
}

/**
 * Slow posture overlay layered above authored idle motion. It intentionally
 * contains rotations only: posture must never translate the avatar root.
 */
export class NaturalPostureController {
  private lean = 0;
  private tilt = 0;
  private openness = 0;
  private elbow = 0;
  private headPitch = 0;
  private thinking = 0;
  private asymmetry = 0;
  private targetAsymmetry = 0;
  private nextAsymmetryAt = 0;

  constructor(private readonly random: () => number = Math.random) {}

  reset(elapsed = 0): void {
    this.lean = 0;
    this.tilt = 0;
    this.openness = 0;
    this.elbow = 0;
    this.headPitch = 0;
    this.thinking = 0;
    this.asymmetry = 0;
    this.targetAsymmetry = 0;
    this.nextAsymmetryAt = elapsed + 3.5 + this.random() * 3.5;
  }

  update(delta: number, elapsed: number, state: CharacterState): VrmPostureFrame {
    const target = stateTarget(state);
    const response = state === "noticing" ? 5.0 : state === "sleeping" ? 1.8 : 2.7;

    this.lean = approach(this.lean, target.lean, response, delta);
    this.tilt = approach(this.tilt, target.tilt, response, delta);
    this.openness = approach(this.openness, target.openness, response, delta);
    this.elbow = approach(this.elbow, target.elbow, response, delta);
    this.headPitch = approach(this.headPitch, target.headPitch, response, delta);
    this.thinking = approach(this.thinking, target.thinking, 3.6, delta);

    if (elapsed >= this.nextAsymmetryAt) {
      const amplitude = state === "sleeping" ? 0.18 : state === "noticing" ? 0.42 : 0.34;
      this.targetAsymmetry = (this.random() * 2 - 1) * amplitude;
      this.nextAsymmetryAt = elapsed + 4.5 + this.random() * 5.0;
    }
    this.asymmetry = approach(this.asymmetry, this.targetAsymmetry, 0.85, delta);

    const side = clamp(this.asymmetry, -0.5, 0.5);
    const shoulderBias = side * 0.020;
    const armSwing = side * 0.025;
    const wristBias = side * 0.015;
    const think = this.thinking;

    return {
      spine: [this.lean * 0.38, -0.010 * think, -this.tilt * 0.28],
      chest: [this.lean * 0.62, side * 0.010 - 0.025 * think, this.tilt * 0.55 + 0.015 * think],
      neck: [this.headPitch * 0.30, -side * 0.008, -this.tilt * 0.25],
      head: [this.headPitch * 0.70, -side * 0.012, this.tilt * 0.34],
      leftShoulder: [0, 0, -this.openness - shoulderBias],
      rightShoulder: [0, 0, this.openness - shoulderBias - 0.010 * think],
      leftUpperArm: [armSwing + 0.025 * think, -side * 0.010, this.openness * 0.30 + side * 0.012 + 0.035 * think],
      rightUpperArm: [-armSwing - 0.16 * think, -side * 0.010 + 0.08 * think, this.openness * 0.30 + side * 0.012 - 0.16 * think],
      leftLowerArm: [-this.elbow * (1 + side * 0.18) - 0.08 * think, -0.02 * think, side * 0.010],
      rightLowerArm: [-this.elbow * (1 - side * 0.18) - 0.68 * think, 0.08 * think, side * 0.010 + 0.05 * think],
      leftHand: [0.010 + side * 0.006, 0, -wristBias],
      rightHand: [0.010 - side * 0.006 + 0.08 * think, -0.04 * think, -wristBias - 0.03 * think],
    };
  }
}
