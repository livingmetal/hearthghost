import assert from "node:assert/strict";
import test from "node:test";
import { VectorKeyframeTrack } from "three";

import {
  reanchorHipsPositionTrack,
  targetBaseAnimationWeight,
} from "../.test-dist/character/vrm-base-animation.js";
import { ProceduralIdleBaseMotion } from "../.test-dist/character/vrm-base-motion.js";

function sequenceRandom(values) {
  let index = 0;
  return () => {
    const value = values[index % values.length];
    index += 1;
    return value;
  };
}

function advance(motion, state, seconds) {
  let frame;
  const steps = Math.ceil(seconds / 0.1);
  for (let index = 0; index < steps; index += 1) {
    frame = motion.update(0.1, state);
  }
  return frame;
}

test("procedural idle shifts weight through bones without root translation", () => {
  const motion = new ProceduralIdleBaseMotion(sequenceRandom([0.8, 0.9, 0.6, 0.2]));
  motion.reset(0);

  const frame = advance(motion, "engaged", 8);

  assert.ok(Math.abs(frame.weight) > 0.1);
  assert.ok(frame.hips[2] * frame.chest[2] < 0, "torso should counter-balance pelvis roll");
  assert.notEqual(frame.leftLowerLeg[0], frame.rightLowerLeg[0]);
  assert.equal("rootX" in frame, false);
  assert.equal("rootZ" in frame, false);
  assert.equal("position" in frame, false);
});

test("sleeping settles weight toward center and remains subtle", () => {
  const motion = new ProceduralIdleBaseMotion(sequenceRandom([0.9, 0.9, 0.4, 0.7]));
  motion.reset(0);

  const active = advance(motion, "speaking", 8);
  const sleeping = advance(motion, "sleeping", 8);

  assert.ok(Math.abs(sleeping.weight) < Math.abs(active.weight));
  assert.ok(Math.abs(sleeping.hips[2]) < 0.01);
  assert.ok(Math.abs(sleeping.chest[2]) < 0.01);
});

test("base-motion rotations stay intentionally small", () => {
  const motion = new ProceduralIdleBaseMotion(sequenceRandom([0.1, 0.9, 0.2, 0.8]));
  motion.reset(0);

  for (const state of ["listening", "thinking", "speaking", "engaged"]) {
    const frame = advance(motion, state, 7);
    for (const rotation of [
      frame.hips,
      frame.spine,
      frame.chest,
      frame.neck,
      frame.head,
      frame.leftShoulder,
      frame.rightShoulder,
      frame.leftUpperLeg,
      frame.rightUpperLeg,
      frame.leftLowerLeg,
      frame.rightLowerLeg,
    ]) {
      for (const component of rotation) {
        assert.ok(Math.abs(component) < 0.06, `${state} base motion exceeded the micro-motion envelope`);
      }
    }
  }
});

test("VRMA hips translation is re-anchored and bounded around model rest", () => {
  const track = new VectorKeyframeTrack(
    "NormalizedHips.position",
    [0, 1, 2],
    [
      10, 20, 30,
      10.5, 19.0, 30.5,
      9.0, 21.0, 28.0,
    ],
  );
  const anchored = reanchorHipsPositionTrack(track, [1, 2, 3]);
  const values = Array.from(anchored.values);
  const epsilon = 1e-6;

  assert.deepEqual(values.slice(0, 3), [1, 2, 3]);
  for (let index = 0; index + 2 < values.length; index += 3) {
    assert.ok(values[index] >= 1 - 0.055 - epsilon && values[index] <= 1 + 0.055 + epsilon);
    assert.ok(values[index + 1] >= 2 - 0.030 - epsilon && values[index + 1] <= 2 + 0.050 + epsilon);
    assert.ok(values[index + 2] >= 3 - 0.035 - epsilon && values[index + 2] <= 3 + 0.035 + epsilon);
  }
});

test("authored idle blend remains subtle and state-aware", () => {
  const states = ["sleeping", "thinking", "listening", "engaged", "noticing", "speaking"];
  for (const state of states) {
    const weight = targetBaseAnimationWeight(state);
    assert.ok(weight >= 0 && weight < 0.9, `${state} authored idle weight must remain bounded`);
  }
  assert.ok(targetBaseAnimationWeight("sleeping") < targetBaseAnimationWeight("engaged"));
  assert.ok(targetBaseAnimationWeight("thinking") < targetBaseAnimationWeight("listening"));
});
