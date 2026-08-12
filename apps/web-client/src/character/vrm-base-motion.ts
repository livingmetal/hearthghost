import type { CharacterState } from "./semantic.js";

export interface VrmBaseMotionFrame {
  readonly hips: readonly [number, number, number];
  readonly spine: readonly [number, number, number];
  readonly chest: readonly [number, number, number];
  readonly neck: readonly [number, number, number];
  readonly head: readonly [number, number, number];
  readonly leftShoulder: readonly [number, number, number];
  readonly rightShoulder: readonly [number, number, number];
  readonly leftUpperLeg: readonly [number, number, number];
  readonly rightUpperLeg: readonly [number, number, number];
  readonly leftLowerLeg: readonly [number, number, number];
  readonly rightLowerLeg: readonly [number, number, number];
  readonly weight: number;
}

export interface VrmBaseMotionSource {
  reset(elapsed?: number): void;
  update(delta: number, state: CharacterState): VrmBaseMotionFrame;
}

type RandomSource = () => number;

const ZERO: readonly [number, number, number] = Object.freeze([0, 0, 0]);
const ACTIVE_WEIGHT = 0.68;

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, value));
}

function activeScale(state: CharacterState): number {
  switch (state) {
    case "sleeping":
      return 0.18;
    case "thinking":
      return 0.72;
    case "speaking":
      return 1.0;
    case "noticing":
      return 0.88;
    case "listening":
      return 0.78;
    case "engaged":
      return 0.74;
  }
}

/**
 * Foot-planted procedural idle motion.
 *
 * This intentionally has no root-position output. Idle motion may redistribute
 * weight through the humanoid chain, but only explicit semantic movement is
 * allowed to translate the VRM scene. The interface is deliberately narrow so
 * a reviewed VRMA/AnimationMixer-backed source can replace this implementation
 * later without changing gesture, gaze, expression, or client transport code.
 */
export class ProceduralIdleBaseMotion implements VrmBaseMotionSource {
  private elapsed = 0;
  private weight = 0;
  private targetWeight = 0;
  private nextShiftAt = 3.5;
  private previousNonZeroTarget = ACTIVE_WEIGHT;

  constructor(private readonly random: RandomSource = Math.random) {}

  reset(elapsed = 0): void {
    this.elapsed = elapsed;
    this.weight = 0;
    this.targetWeight = 0;
    this.nextShiftAt = elapsed + 3.2 + this.random() * 2.4;
  }

  update(delta: number, state: CharacterState): VrmBaseMotionFrame {
    const boundedDelta = Math.max(0, Math.min(delta, 0.1));
    this.elapsed += boundedDelta;

    if (state === "sleeping") {
      this.targetWeight = 0;
      this.nextShiftAt = Math.max(this.nextShiftAt, this.elapsed + 2.5);
    } else if (this.elapsed >= this.nextShiftAt) {
      this.chooseNextWeightTarget();
      this.nextShiftAt = this.elapsed + 3.8 + this.random() * 3.8;
    }

    const response = state === "speaking" ? 1.05 : state === "noticing" ? 0.92 : 0.68;
    const blend = 1 - Math.exp(-response * boundedDelta);
    this.weight += (this.targetWeight - this.weight) * blend;

    const scale = activeScale(state);
    const micro = Math.sin(this.elapsed * 0.62 + 0.45) * 0.075 * scale;
    const weight = clamp((this.weight + micro) * scale, -0.82, 0.82);
    const rightSupport = Math.max(0, weight);
    const leftSupport = Math.max(0, -weight);
    const freeLeft = rightSupport;
    const freeRight = leftSupport;
    const breathingCounter = Math.sin(this.elapsed * 0.37 + 1.1) * 0.003 * scale;

    return {
      // Pelvis tips slightly toward the supporting leg. The torso counters it,
      // which reads as weight transfer rather than whole-model translation.
      hips: [0, breathingCounter, -weight * 0.024],
      spine: [0, -breathingCounter * 0.7, weight * 0.009],
      chest: [0, -breathingCounter, weight * 0.016],
      neck: [0, breathingCounter * 0.45, -weight * 0.004],
      head: [0, -breathingCounter * 0.5, -weight * 0.006],

      // Shoulder compensation is deliberately smaller than the pelvis/chest
      // motion so the upper body stays conversational rather than pendular.
      leftShoulder: [0, 0, -weight * 0.004],
      rightShoulder: [0, 0, -weight * 0.004],

      // The supporting leg straightens slightly while the free leg softens at
      // the knee. Both feet remain near their rest placement because no scene
      // or hips-position translation is emitted by this base motion source.
      leftUpperLeg: [0.010 + freeLeft * 0.012, 0, -weight * 0.006],
      rightUpperLeg: [0.010 + freeRight * 0.012, 0, -weight * 0.006],
      leftLowerLeg: [-0.018 - freeLeft * 0.020 + leftSupport * 0.006, 0, 0],
      rightLowerLeg: [-0.018 - freeRight * 0.020 + rightSupport * 0.006, 0, 0],
      weight,
    };
  }

  private chooseNextWeightTarget(): void {
    const roll = this.random();
    let next = roll < 0.18
      ? 0
      : roll < 0.59
        ? -ACTIVE_WEIGHT
        : ACTIVE_WEIGHT;

    // Avoid visibly repeating the same lean for two long holds in a row.
    if (next !== 0 && next === this.previousNonZeroTarget) {
      next = -next;
    }
    if (next !== 0) {
      this.previousNonZeroTarget = next;
    }
    this.targetWeight = next;
  }
}

export const ZERO_BASE_MOTION_FRAME: VrmBaseMotionFrame = Object.freeze({
  hips: ZERO,
  spine: ZERO,
  chest: ZERO,
  neck: ZERO,
  head: ZERO,
  leftShoulder: ZERO,
  rightShoulder: ZERO,
  leftUpperLeg: ZERO,
  rightUpperLeg: ZERO,
  leftLowerLeg: ZERO,
  rightLowerLeg: ZERO,
  weight: 0,
});
