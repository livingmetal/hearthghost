import type { HearthGhostCharacterId } from "./catalog.js";
import type { CharacterState } from "./semantic.js";

export type PostureRotation = readonly [number, number, number];

type PostureBoneName =
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

export interface VrmPostureFrame extends Readonly<Record<PostureBoneName, PostureRotation>> {}

interface PostureScalarState {
  readonly lean: number;
  readonly tilt: number;
  readonly openness: number;
  readonly elbow: number;
  readonly headPitch: number;
}

interface PostureVariant {
  readonly id: string;
  readonly weight: number;
  readonly bones: Readonly<Partial<Record<PostureBoneName, PostureRotation>>>;
}

interface CharacterPostureProfile {
  readonly motionScale: number;
  readonly asymmetryScale: number;
  readonly opennessBias: number;
  readonly elbowBias: number;
  readonly variants: Readonly<Partial<Record<CharacterState, readonly PostureVariant[]>>>;
}

const POSTURE_BONES: readonly PostureBoneName[] = Object.freeze([
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

const ZERO_ROTATION: PostureRotation = Object.freeze([0, 0, 0]);

function variant(
  id: string,
  weight: number,
  bones: Partial<Record<PostureBoneName, PostureRotation>>,
): PostureVariant {
  return Object.freeze({ id, weight, bones: Object.freeze(bones) });
}

const YOUNGHEE_PROFILE: CharacterPostureProfile = Object.freeze({
  motionScale: 1.0,
  asymmetryScale: 1.0,
  opennessBias: 0.004,
  elbowBias: 0.004,
  variants: Object.freeze({
    noticing: Object.freeze([
      variant("younghee.noticing.brighten", 0.42, {
        spine: [-0.008, 0, 0],
        chest: [-0.018, 0, 0.012],
        head: [-0.014, 0, 0.012],
        leftShoulder: [0, 0, -0.012],
        rightShoulder: [0, 0, 0.010],
      }),
      variant("younghee.noticing.catch-side", 0.34, {
        chest: [-0.010, 0.020, -0.008],
        neck: [-0.004, -0.014, -0.010],
        head: [-0.010, -0.026, -0.020],
        rightShoulder: [0, 0, -0.010],
      }),
      variant("younghee.noticing.small-freeze", 0.24, {
        chest: [-0.006, -0.006, 0.010],
        head: [-0.016, 0.008, 0.006],
        leftUpperArm: [0.018, -0.006, 0.010],
        rightUpperArm: [-0.014, 0.006, -0.008],
      }),
    ]),
    thinking: Object.freeze([
      variant("younghee.thinking.chin-touch", 0.32, {
        chest: [0, -0.020, 0.012],
        head: [0.010, 0, 0.025],
        rightShoulder: [0, 0, -0.010],
        rightUpperArm: [-0.16, 0.08, -0.16],
        rightLowerArm: [-0.66, 0.08, 0.05],
        rightHand: [0.08, -0.04, -0.03],
        leftLowerArm: [-0.07, -0.02, 0.02],
      }),
      variant("younghee.thinking.head-tilt", 0.28, {
        chest: [0.005, 0.014, -0.010],
        neck: [0.006, -0.010, 0.024],
        head: [0.008, -0.018, 0.052],
        leftShoulder: [0, 0, 0.012],
        rightShoulder: [0, 0, -0.006],
        leftLowerArm: [-0.10, 0, 0.015],
        rightLowerArm: [-0.07, 0, -0.010],
      }),
      variant("younghee.thinking.soft-closed", 0.20, {
        chest: [0.012, -0.018, 0.008],
        head: [0.018, 0.012, 0.016],
        leftUpperArm: [0.025, -0.025, 0.028],
        rightUpperArm: [-0.025, 0.025, -0.028],
        leftLowerArm: [-0.15, -0.035, 0.025],
        rightLowerArm: [-0.14, 0.035, -0.025],
      }),
      variant("younghee.thinking.look-up", 0.20, {
        spine: [0.004, 0, 0],
        chest: [0.004, 0.012, 0.006],
        neck: [-0.018, -0.012, 0.010],
        head: [-0.036, -0.018, 0.020],
        leftLowerArm: [-0.055, -0.010, 0.010],
        rightLowerArm: [-0.080, 0.016, -0.012],
      }),
    ]),
    listening: Object.freeze([
      variant("younghee.listening.forward", 0.34, {
        spine: [-0.010, 0, 0],
        chest: [-0.016, 0, 0.008],
        head: [-0.008, 0, 0.012],
        leftLowerArm: [-0.035, 0, 0],
      }),
      variant("younghee.listening.soft-side", 0.28, {
        chest: [-0.008, 0.012, -0.010],
        neck: [0, -0.008, -0.010],
        head: [-0.004, -0.014, -0.022],
        rightShoulder: [0, 0, -0.010],
      }),
      variant("younghee.listening.upright-open", 0.22, {
        spine: [-0.004, 0, 0],
        chest: [-0.010, -0.006, 0.006],
        head: [-0.006, 0.008, 0.006],
        leftShoulder: [0, 0, -0.012],
        rightShoulder: [0, 0, 0.010],
        leftLowerArm: [-0.045, 0, 0.008],
        rightLowerArm: [-0.038, 0, -0.006],
      }),
      variant("younghee.listening.quiet-collected", 0.16, {
        chest: [-0.004, 0.006, -0.004],
        head: [-0.002, -0.008, -0.010],
        leftUpperArm: [0.012, -0.012, 0.016],
        rightUpperArm: [-0.010, 0.012, -0.014],
        leftLowerArm: [-0.095, -0.012, 0.012],
        rightLowerArm: [-0.085, 0.012, -0.010],
      }),
    ]),
    speaking: Object.freeze([
      variant("younghee.speaking.open", 0.32, {
        chest: [-0.006, 0, 0.010],
        leftShoulder: [0, 0, -0.014],
        rightShoulder: [0, 0, 0.010],
        leftUpperArm: [0.016, -0.008, 0.012],
        rightUpperArm: [-0.010, 0.006, -0.008],
      }),
      variant("younghee.speaking.centered", 0.24, {
        chest: [-0.004, -0.008, -0.006],
        head: [0, 0.010, 0.010],
        leftLowerArm: [-0.050, 0, 0.010],
        rightLowerArm: [-0.035, 0, -0.008],
      }),
      variant("younghee.speaking.left-present", 0.24, {
        chest: [-0.008, 0.012, -0.004],
        head: [-0.002, -0.008, -0.006],
        leftShoulder: [0, 0, -0.016],
        leftUpperArm: [0.028, -0.012, 0.018],
        leftLowerArm: [-0.080, -0.018, 0.018],
        rightLowerArm: [-0.030, 0, -0.006],
      }),
      variant("younghee.speaking.right-present", 0.20, {
        chest: [-0.008, -0.012, 0.004],
        head: [-0.002, 0.008, 0.006],
        rightShoulder: [0, 0, 0.014],
        rightUpperArm: [-0.026, 0.012, -0.016],
        rightLowerArm: [-0.075, 0.018, -0.016],
        leftLowerArm: [-0.032, 0, 0.006],
      }),
    ]),
    engaged: Object.freeze([
      variant("younghee.engaged.left-soft", 0.25, {
        chest: [0, 0.008, -0.006],
        head: [0, -0.006, -0.010],
        leftShoulder: [0, 0, 0.008],
      }),
      variant("younghee.engaged.right-soft", 0.25, {
        chest: [0, -0.008, 0.006],
        head: [0, 0.006, 0.010],
        rightShoulder: [0, 0, -0.008],
      }),
      variant("younghee.engaged.casual-open", 0.27, {
        spine: [-0.002, 0, 0],
        chest: [-0.004, 0, 0.008],
        head: [-0.002, 0, 0.006],
        leftShoulder: [0, 0, -0.010],
        rightShoulder: [0, 0, 0.008],
        leftLowerArm: [-0.035, 0, 0.006],
        rightLowerArm: [-0.030, 0, -0.004],
      }),
      variant("younghee.engaged.quiet-collected", 0.23, {
        chest: [0.004, -0.006, -0.004],
        head: [0.004, 0.006, -0.006],
        leftUpperArm: [0.010, -0.010, 0.012],
        rightUpperArm: [-0.010, 0.010, -0.012],
        leftLowerArm: [-0.070, -0.010, 0.010],
        rightLowerArm: [-0.065, 0.010, -0.010],
      }),
    ]),
  }),
});

const CHEOLSU_PROFILE: CharacterPostureProfile = Object.freeze({
  motionScale: 0.82,
  asymmetryScale: 0.72,
  opennessBias: -0.004,
  elbowBias: 0.010,
  variants: Object.freeze({
    noticing: Object.freeze([
      variant("cheolsu.noticing.upright-catch", 0.46, {
        spine: [-0.004, 0, 0],
        chest: [-0.010, 0, 0.002],
        neck: [-0.008, 0, 0],
        head: [-0.012, 0, 0],
      }),
      variant("cheolsu.noticing.measured-side", 0.32, {
        chest: [-0.006, -0.012, 0.004],
        neck: [-0.004, 0.010, 0.004],
        head: [-0.008, 0.020, 0.006],
        rightShoulder: [0, 0, -0.006],
      }),
      variant("cheolsu.noticing.slight-back", 0.22, {
        spine: [0.006, 0, 0],
        chest: [0.008, 0, 0],
        head: [-0.014, -0.006, 0],
        leftLowerArm: [-0.025, 0, 0],
        rightLowerArm: [-0.025, 0, 0],
      }),
    ]),
    thinking: Object.freeze([
      variant("cheolsu.thinking.chin-rest", 0.28, {
        chest: [0.014, -0.014, 0.004],
        head: [0.018, 0.010, -0.012],
        rightUpperArm: [-0.12, 0.06, -0.12],
        rightLowerArm: [-0.58, 0.07, 0.035],
        rightHand: [0.065, -0.025, -0.020],
      }),
      variant("cheolsu.thinking.downward", 0.30, {
        spine: [0.010, 0, 0],
        chest: [0.015, 0.010, 0],
        neck: [0.022, -0.010, 0],
        head: [0.045, -0.016, -0.008],
        leftLowerArm: [-0.08, 0, 0],
        rightLowerArm: [-0.10, 0, 0],
      }),
      variant("cheolsu.thinking.contained", 0.24, {
        chest: [0.010, -0.010, 0],
        leftUpperArm: [0.018, -0.018, 0.018],
        rightUpperArm: [-0.018, 0.018, -0.018],
        leftLowerArm: [-0.16, -0.025, 0.018],
        rightLowerArm: [-0.16, 0.025, -0.018],
        head: [0.020, 0.008, 0],
      }),
      variant("cheolsu.thinking.side-consider", 0.18, {
        spine: [0.006, 0, 0],
        chest: [0.010, 0.012, -0.004],
        neck: [0.012, -0.012, -0.004],
        head: [0.022, -0.022, -0.008],
        leftLowerArm: [-0.070, -0.008, 0.006],
        rightLowerArm: [-0.095, 0.014, -0.008],
      }),
    ]),
    listening: Object.freeze([
      variant("cheolsu.listening.upright", 0.34, {
        chest: [-0.008, 0, 0],
        neck: [-0.004, 0, 0],
        head: [-0.006, 0, 0],
      }),
      variant("cheolsu.listening.forward", 0.26, {
        spine: [-0.008, 0, 0],
        chest: [-0.012, -0.006, 0],
        head: [-0.006, 0.008, -0.006],
      }),
      variant("cheolsu.listening.still", 0.24, {
        spine: [-0.002, 0, 0],
        chest: [-0.004, 0.004, 0],
        head: [-0.004, -0.004, 0],
        leftLowerArm: [-0.040, 0, 0],
        rightLowerArm: [-0.040, 0, 0],
      }),
      variant("cheolsu.listening.side-attentive", 0.16, {
        chest: [-0.006, 0.008, -0.004],
        neck: [-0.004, -0.008, -0.004],
        head: [-0.006, -0.014, -0.008],
        leftShoulder: [0, 0, 0.004],
      }),
    ]),
    speaking: Object.freeze([
      variant("cheolsu.speaking.restrained", 0.38, {
        chest: [-0.004, 0, 0],
        leftLowerArm: [-0.028, 0, 0],
        rightLowerArm: [-0.024, 0, 0],
      }),
      variant("cheolsu.speaking.open-small", 0.24, {
        chest: [-0.005, -0.006, 0.004],
        leftShoulder: [0, 0, -0.008],
        rightShoulder: [0, 0, 0.006],
        leftUpperArm: [0.010, 0, 0.008],
      }),
      variant("cheolsu.speaking.measured-side", 0.20, {
        chest: [-0.004, 0.008, -0.002],
        head: [-0.002, -0.006, -0.004],
        leftUpperArm: [0.014, -0.006, 0.008],
        leftLowerArm: [-0.048, -0.008, 0.006],
        rightLowerArm: [-0.025, 0, 0],
      }),
      variant("cheolsu.speaking.upright", 0.18, {
        spine: [-0.003, 0, 0],
        chest: [-0.005, 0, 0.002],
        head: [-0.003, 0, 0],
        leftLowerArm: [-0.035, 0, 0],
        rightLowerArm: [-0.032, 0, 0],
      }),
    ]),
    engaged: Object.freeze([
      variant("cheolsu.engaged.balanced", 0.30, {
        chest: [0.002, 0, 0],
        head: [0.002, 0, 0],
      }),
      variant("cheolsu.engaged.side", 0.22, {
        chest: [0.003, -0.006, 0.004],
        head: [0.002, 0.008, 0.006],
      }),
      variant("cheolsu.engaged.rest-upright", 0.28, {
        spine: [-0.002, 0, 0],
        chest: [-0.003, 0, 0],
        neck: [-0.002, 0, 0],
        leftLowerArm: [-0.030, 0, 0],
        rightLowerArm: [-0.030, 0, 0],
      }),
      variant("cheolsu.engaged.contained", 0.20, {
        chest: [0.004, 0.004, -0.002],
        head: [0.004, -0.004, -0.004],
        leftUpperArm: [0.008, -0.008, 0.010],
        rightUpperArm: [-0.008, 0.008, -0.010],
        leftLowerArm: [-0.060, -0.008, 0.006],
        rightLowerArm: [-0.060, 0.008, -0.006],
      }),
    ]),
  }),
});

const GENERIC_PROFILE: CharacterPostureProfile = Object.freeze({
  motionScale: 0.90,
  asymmetryScale: 0.85,
  opennessBias: 0,
  elbowBias: 0.006,
  variants: Object.freeze({}),
});

const PROFILES: Readonly<Record<HearthGhostCharacterId, CharacterPostureProfile>> = Object.freeze({
  younghee: YOUNGHEE_PROFILE,
  cheolsu: CHEOLSU_PROFILE,
});

function profileFor(characterId: HearthGhostCharacterId | null): CharacterPostureProfile {
  return characterId === null ? GENERIC_PROFILE : PROFILES[characterId];
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
      return { lean: 0.022, tilt: 0, openness: -0.018, elbow: 0.040, headPitch: 0.045 };
    case "thinking":
      return { lean: 0.014, tilt: 0.010, openness: -0.008, elbow: 0.060, headPitch: 0.018 };
    case "listening":
      return { lean: -0.012, tilt: 0.008, openness: 0.010, elbow: 0.050, headPitch: -0.010 };
    case "noticing":
      return { lean: -0.010, tilt: 0.004, openness: 0.025, elbow: 0.030, headPitch: -0.015 };
    case "speaking":
      return { lean: -0.006, tilt: 0.006, openness: 0.018, elbow: 0.055, headPitch: -0.006 };
    case "engaged":
      return { lean: 0, tilt: 0.006, openness: 0.008, elbow: 0.045, headPitch: 0 };
  }
}

function emptyVariantPose(): Record<PostureBoneName, [number, number, number]> {
  return Object.fromEntries(
    POSTURE_BONES.map((bone) => [bone, [0, 0, 0]]),
  ) as Record<PostureBoneName, [number, number, number]>;
}

function variantDwellSeconds(state: CharacterState, random: () => number): number {
  const [minimum, spread] = state === "noticing"
    ? [1.2, 1.0]
    : state === "thinking"
      ? [2.8, 2.8]
      : state === "speaking"
        ? [3.6, 3.4]
        : state === "listening"
          ? [4.2, 3.8]
          : state === "engaged"
            ? [5.5, 4.5]
            : [8.0, 4.0];
  return minimum + random() * spread;
}

function chooseVariant(
  variants: readonly PostureVariant[],
  previousId: string | null,
  random: () => number,
): PostureVariant {
  const candidates = variants.length > 1 && previousId !== null
    ? variants.filter((candidate) => candidate.id !== previousId)
    : variants;
  const total = candidates.reduce((sum, candidate) => sum + candidate.weight, 0);
  let cursor = random() * total;
  for (const candidate of candidates) {
    cursor -= candidate.weight;
    if (cursor <= 0) {
      return candidate;
    }
  }
  return candidates[candidates.length - 1] ?? variants[0]!;
}

/**
 * Character-specific posture overlay layered above authored idle motion.
 * State describes intent; the profile and selected variant describe how this
 * particular character performs that state. The frame contains rotations only.
 */
export class NaturalPostureController {
  private readonly profile: CharacterPostureProfile;
  private lean = 0;
  private tilt = 0;
  private openness = 0;
  private elbow = 0;
  private headPitch = 0;
  private asymmetry = 0;
  private targetAsymmetry = 0;
  private nextAsymmetryAt = 0;
  private lastState: CharacterState | null = null;
  private variantId: string | null = null;
  private nextVariantAt = 0;
  private readonly variantCurrent = emptyVariantPose();
  private readonly variantTarget = emptyVariantPose();

  constructor(
    characterId: HearthGhostCharacterId | null = null,
    private readonly random: () => number = Math.random,
  ) {
    this.profile = profileFor(characterId);
  }

  get currentVariantId(): string | null {
    return this.variantId;
  }

  reset(elapsed = 0): void {
    this.lean = 0;
    this.tilt = 0;
    this.openness = 0;
    this.elbow = 0;
    this.headPitch = 0;
    this.asymmetry = 0;
    this.targetAsymmetry = 0;
    this.nextAsymmetryAt = elapsed + 3.5 + this.random() * 3.5;
    this.lastState = null;
    this.variantId = null;
    this.nextVariantAt = elapsed;
    for (const bone of POSTURE_BONES) {
      this.variantCurrent[bone] = [0, 0, 0];
      this.variantTarget[bone] = [0, 0, 0];
    }
  }

  update(delta: number, elapsed: number, state: CharacterState): VrmPostureFrame {
    const target = stateTarget(state);
    const response = state === "noticing" ? 5.0 : state === "sleeping" ? 1.8 : 2.7;
    const scale = this.profile.motionScale;

    this.lean = approach(this.lean, target.lean * scale, response, delta);
    this.tilt = approach(this.tilt, target.tilt * scale, response, delta);
    this.openness = approach(
      this.openness,
      target.openness * scale + this.profile.opennessBias,
      response,
      delta,
    );
    this.elbow = approach(
      this.elbow,
      target.elbow * scale + this.profile.elbowBias,
      response,
      delta,
    );
    this.headPitch = approach(this.headPitch, target.headPitch * scale, response, delta);

    if (elapsed >= this.nextAsymmetryAt) {
      const stateAmplitude = state === "sleeping" ? 0.18 : state === "noticing" ? 0.42 : 0.34;
      this.targetAsymmetry = (this.random() * 2 - 1)
        * stateAmplitude
        * this.profile.asymmetryScale;
      this.nextAsymmetryAt = elapsed + 4.5 + this.random() * 5.0;
    }
    this.asymmetry = approach(this.asymmetry, this.targetAsymmetry, 0.85, delta);

    if (state !== this.lastState || elapsed >= this.nextVariantAt) {
      this.selectVariant(state, elapsed);
      this.lastState = state;
    }
    this.blendVariant(delta);

    const side = clamp(this.asymmetry, -0.5, 0.5);
    const shoulderBias = side * 0.020;
    const armSwing = side * 0.025;
    const wristBias = side * 0.015;

    const base: VrmPostureFrame = {
      spine: [this.lean * 0.38, 0, -this.tilt * 0.28],
      chest: [this.lean * 0.62, side * 0.010, this.tilt * 0.55],
      neck: [this.headPitch * 0.30, -side * 0.008, -this.tilt * 0.25],
      head: [this.headPitch * 0.70, -side * 0.012, this.tilt * 0.34],
      leftShoulder: [0, 0, -this.openness - shoulderBias],
      rightShoulder: [0, 0, this.openness - shoulderBias],
      leftUpperArm: [armSwing, -side * 0.010, this.openness * 0.30 + side * 0.012],
      rightUpperArm: [-armSwing, -side * 0.010, this.openness * 0.30 + side * 0.012],
      leftLowerArm: [-this.elbow * (1 + side * 0.18), 0, side * 0.010],
      rightLowerArm: [-this.elbow * (1 - side * 0.18), 0, side * 0.010],
      leftHand: [0.010 + side * 0.006, 0, -wristBias],
      rightHand: [0.010 - side * 0.006, 0, -wristBias],
    };

    return Object.fromEntries(POSTURE_BONES.map((bone) => {
      const foundation = base[bone];
      const detail = this.variantCurrent[bone];
      return [bone, [
        foundation[0] + detail[0] * scale,
        foundation[1] + detail[1] * scale,
        foundation[2] + detail[2] * scale,
      ] as PostureRotation];
    })) as unknown as VrmPostureFrame;
  }

  private selectVariant(state: CharacterState, elapsed: number): void {
    const variants = this.profile.variants[state] ?? [];
    for (const bone of POSTURE_BONES) {
      this.variantTarget[bone] = [0, 0, 0];
    }
    if (variants.length === 0) {
      this.variantId = null;
      this.nextVariantAt = elapsed + variantDwellSeconds(state, this.random);
      return;
    }

    const selected = chooseVariant(variants, this.variantId, this.random);
    this.variantId = selected.id;
    for (const [bone, rotation] of Object.entries(selected.bones) as [PostureBoneName, PostureRotation][]) {
      this.variantTarget[bone] = [rotation[0], rotation[1], rotation[2]];
    }
    this.nextVariantAt = elapsed + variantDwellSeconds(state, this.random);
  }

  private blendVariant(delta: number): void {
    const response = 3.2;
    for (const bone of POSTURE_BONES) {
      const current = this.variantCurrent[bone];
      const target = this.variantTarget[bone];
      current[0] = approach(current[0], target[0], response, delta);
      current[1] = approach(current[1], target[1], response, delta);
      current[2] = approach(current[2], target[2], response, delta);
    }
  }
}

export const ZERO_POSTURE_ROTATION = ZERO_ROTATION;
