import assert from "node:assert/strict";
import test from "node:test";

import { NaturalPostureController } from "../.test-dist/character/vrm-posture.js";

function sequence(values) {
  let index = 0;
  return () => values[index++ % values.length];
}

function maxAbs(rotation) {
  return Math.max(...rotation.map((value) => Math.abs(value)));
}

test("posture frames contain rotations only and stay within subtle bounds", () => {
  const posture = new NaturalPostureController(sequence([0.9, 0.1, 0.7, 0.3]));
  posture.reset(0);
  let frame;
  for (let index = 0; index < 240; index += 1) {
    frame = posture.update(1 / 60, index / 60, "engaged");
  }

  assert.equal("position" in frame, false);
  assert.equal("rootX" in frame, false);
  assert.equal("rootZ" in frame, false);
  for (const rotation of Object.values(frame)) {
    assert.ok(maxAbs(rotation) <= 0.12);
  }
});

test("listening settles into a slight attentive lean instead of a symmetric mannequin pose", () => {
  const posture = new NaturalPostureController(sequence([1, 0, 1, 0]));
  posture.reset(0);
  let frame;
  for (let index = 0; index < 600; index += 1) {
    frame = posture.update(1 / 60, index / 60, "listening");
  }

  assert.ok(frame.chest[0] < 0);
  assert.notEqual(frame.leftLowerArm[0], frame.rightLowerArm[0]);
  assert.notEqual(frame.leftShoulder[2], -frame.rightShoulder[2]);
});

test("state changes ease toward the new posture rather than snapping", () => {
  const posture = new NaturalPostureController(() => 0.5);
  posture.reset(0);
  for (let index = 0; index < 180; index += 1) {
    posture.update(1 / 60, index / 60, "sleeping");
  }
  const before = posture.update(1 / 60, 3.01, "sleeping");
  const firstListening = posture.update(1 / 60, 3.02, "listening");

  assert.ok(Math.abs(firstListening.head[0] - before.head[0]) < 0.01);
  assert.ok(Math.abs(firstListening.chest[0] - before.chest[0]) < 0.01);
});

test("noticing becomes more open while sleeping remains subdued", () => {
  const sleeping = new NaturalPostureController(() => 0.5);
  const noticing = new NaturalPostureController(() => 0.5);
  sleeping.reset(0);
  noticing.reset(0);

  let sleepingFrame;
  let noticingFrame;
  for (let index = 0; index < 600; index += 1) {
    const elapsed = index / 60;
    sleepingFrame = sleeping.update(1 / 60, elapsed, "sleeping");
    noticingFrame = noticing.update(1 / 60, elapsed, "noticing");
  }

  assert.ok(Math.abs(noticingFrame.leftShoulder[2]) > Math.abs(sleepingFrame.leftShoulder[2]));
  assert.ok(noticingFrame.head[0] < sleepingFrame.head[0]);
});
