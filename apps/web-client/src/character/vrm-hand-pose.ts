import type { CharacterSide } from "./semantic.js";

export const LEFT_FINGER_BONE_NAMES = [
  "leftThumbMetacarpal",
  "leftThumbProximal",
  "leftThumbDistal",
  "leftIndexProximal",
  "leftIndexIntermediate",
  "leftIndexDistal",
  "leftMiddleProximal",
  "leftMiddleIntermediate",
  "leftMiddleDistal",
  "leftRingProximal",
  "leftRingIntermediate",
  "leftRingDistal",
  "leftLittleProximal",
  "leftLittleIntermediate",
  "leftLittleDistal",
] as const;

export const RIGHT_FINGER_BONE_NAMES = [
  "rightThumbMetacarpal",
  "rightThumbProximal",
  "rightThumbDistal",
  "rightIndexProximal",
  "rightIndexIntermediate",
  "rightIndexDistal",
  "rightMiddleProximal",
  "rightMiddleIntermediate",
  "rightMiddleDistal",
  "rightRingProximal",
  "rightRingIntermediate",
  "rightRingDistal",
  "rightLittleProximal",
  "rightLittleIntermediate",
  "rightLittleDistal",
] as const;

export const FINGER_BONE_NAMES = [
  ...LEFT_FINGER_BONE_NAMES,
  ...RIGHT_FINGER_BONE_NAMES,
] as const;

export type FingerBoneName = (typeof FINGER_BONE_NAMES)[number];
export type HandPoseName = "relaxed" | "open" | "point";
export type FingerRotation = readonly [number, number, number];

const FINGER_BONE_SET: ReadonlySet<string> = new Set(FINGER_BONE_NAMES);

const RELAXED_CURL_BY_SUFFIX = Object.freeze({
  ThumbMetacarpal: 0.055,
  ThumbProximal: 0.095,
  ThumbDistal: 0.070,
  IndexProximal: 0.120,
  IndexIntermediate: 0.155,
  IndexDistal: 0.080,
  MiddleProximal: 0.155,
  MiddleIntermediate: 0.195,
  MiddleDistal: 0.100,
  RingProximal: 0.190,
  RingIntermediate: 0.230,
  RingDistal: 0.115,
  LittleProximal: 0.225,
  LittleIntermediate: 0.270,
  LittleDistal: 0.135,
});

const POINT_CURL_BY_SUFFIX = Object.freeze({
  ThumbMetacarpal: 0.070,
  ThumbProximal: 0.115,
  ThumbDistal: 0.075,
  IndexProximal: 0.018,
  IndexIntermediate: 0.014,
  IndexDistal: 0.008,
  MiddleProximal: 0.340,
  MiddleIntermediate: 0.440,
  MiddleDistal: 0.220,
  RingProximal: 0.390,
  RingIntermediate: 0.500,
  RingDistal: 0.250,
  LittleProximal: 0.440,
  LittleIntermediate: 0.550,
  LittleDistal: 0.285,
});

type FingerSuffix = keyof typeof RELAXED_CURL_BY_SUFFIX;

function sideForBone(name: FingerBoneName): CharacterSide {
  return name.startsWith("left") ? "left" : "right";
}

function suffixForBone(name: FingerBoneName): FingerSuffix {
  return name.replace(/^(left|right)/, "") as FingerSuffix;
}

function sideSign(side: CharacterSide): number {
  // Normalized humanoid fingers extend in opposite X directions. Mirroring the
  // Z-axis curl keeps all authored poses symmetric across left and right hands.
  return side === "left" ? -1 : 1;
}

export function isFingerBoneName(name: string): name is FingerBoneName {
  return FINGER_BONE_SET.has(name);
}

export function fingerBonesForSide(side: CharacterSide): readonly FingerBoneName[] {
  return side === "left" ? LEFT_FINGER_BONE_NAMES : RIGHT_FINGER_BONE_NAMES;
}

export function handPoseRotation(name: FingerBoneName, pose: HandPoseName): FingerRotation {
  if (pose === "open") {
    return [0, 0, 0];
  }
  const suffix = suffixForBone(name);
  const curl = pose === "point"
    ? POINT_CURL_BY_SUFFIX[suffix]
    : RELAXED_CURL_BY_SUFFIX[suffix];
  return [0, 0, sideSign(sideForBone(name)) * curl];
}

export function handPoseDelta(
  name: FingerBoneName,
  from: HandPoseName,
  to: HandPoseName,
): FingerRotation {
  const start = handPoseRotation(name, from);
  const end = handPoseRotation(name, to);
  return [
    end[0] - start[0],
    end[1] - start[1],
    end[2] - start[2],
  ];
}
