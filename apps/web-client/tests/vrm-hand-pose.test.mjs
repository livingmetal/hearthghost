import assert from "node:assert/strict";
import test from "node:test";

import {
  FINGER_BONE_NAMES,
  fingerBonesForSide,
  handPoseDelta,
  handPoseRotation,
  isFingerBoneName,
} from "../.test-dist/character/vrm-hand-pose.js";

test("hand pose covers all optional VRM finger bones exactly once", () => {
  assert.equal(FINGER_BONE_NAMES.length, 30);
  assert.equal(new Set(FINGER_BONE_NAMES).size, 30);
  assert.equal(fingerBonesForSide("left").length, 15);
  assert.equal(fingerBonesForSide("right").length, 15);
  assert.equal(isFingerBoneName("leftIndexProximal"), true);
  assert.equal(isFingerBoneName("rightLittleDistal"), true);
  assert.equal(isFingerBoneName("leftHand"), false);
  assert.equal(isFingerBoneName("head"), false);
});

test("relaxed fingers use mirrored curls and progressively soften toward a natural hand", () => {
  const leftIndex = handPoseRotation("leftIndexProximal", "relaxed");
  const rightIndex = handPoseRotation("rightIndexProximal", "relaxed");
  const leftMiddle = handPoseRotation("leftMiddleProximal", "relaxed");
  const leftRing = handPoseRotation("leftRingProximal", "relaxed");
  const leftLittle = handPoseRotation("leftLittleProximal", "relaxed");

  assert.equal(leftIndex[0], 0);
  assert.equal(leftIndex[1], 0);
  assert.equal(leftIndex[2], -rightIndex[2]);
  assert.ok(Math.abs(leftIndex[2]) < Math.abs(leftMiddle[2]));
  assert.ok(Math.abs(leftMiddle[2]) < Math.abs(leftRing[2]));
  assert.ok(Math.abs(leftRing[2]) < Math.abs(leftLittle[2]));
});

test("open pose is neutral and relaxed-to-open delta exactly cancels the curl", () => {
  for (const bone of FINGER_BONE_NAMES) {
    const relaxed = handPoseRotation(bone, "relaxed");
    const open = handPoseRotation(bone, "open");
    const delta = handPoseDelta(bone, "relaxed", "open");

    assert.deepEqual(open, [0, 0, 0]);
    assert.ok(Math.abs(relaxed[2]) <= 0.27);
    assert.equal(relaxed[0] + delta[0], 0);
    assert.equal(relaxed[1] + delta[1], 0);
    assert.equal(relaxed[2] + delta[2], 0);
  }
});

test("point pose extends the index while curling the other three fingers", () => {
  for (const side of ["left", "right"]) {
    const prefix = side === "left" ? "left" : "right";
    const index = Math.abs(handPoseRotation(`${prefix}IndexProximal`, "point")[2]);
    const middle = Math.abs(handPoseRotation(`${prefix}MiddleProximal`, "point")[2]);
    const ring = Math.abs(handPoseRotation(`${prefix}RingProximal`, "point")[2]);
    const little = Math.abs(handPoseRotation(`${prefix}LittleProximal`, "point")[2]);

    assert.ok(index < 0.03);
    assert.ok(middle > 0.30);
    assert.ok(middle < ring);
    assert.ok(ring < little);
  }
});

test("point pose remains mirrored, bounded and reversible from relaxed", () => {
  const left = handPoseRotation("leftRingIntermediate", "point");
  const right = handPoseRotation("rightRingIntermediate", "point");
  assert.equal(left[2], -right[2]);

  for (const bone of FINGER_BONE_NAMES) {
    const relaxed = handPoseRotation(bone, "relaxed");
    const point = handPoseRotation(bone, "point");
    const delta = handPoseDelta(bone, "relaxed", "point");
    assert.ok(Math.abs(point[2]) <= 0.55);
    assert.equal(relaxed[0] + delta[0], point[0]);
    assert.equal(relaxed[1] + delta[1], point[1]);
    assert.equal(relaxed[2] + delta[2], point[2]);
  }
});
