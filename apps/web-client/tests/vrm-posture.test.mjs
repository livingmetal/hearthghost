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

test("engaged posture contains rotations only and stays subtle", () => {
  const posture = new NaturalPostureController("younghee", sequence([0.9, 0.1, 0.7, 0.3]));
  posture.reset(0);
  let frame;
  for (let index = 0; index < 360; index += 1) {
    frame = posture.update(1 / 60, index / 60, "engaged");
  }

  assert.equal("position" in frame, false);
  assert.equal("rootX" in frame, false);
  assert.equal("rootZ" in frame, false);
  for (const rotation of Object.values(frame)) {
    assert.ok(maxAbs(rotation) <= 0.12);
  }
});

test("younghee and cheolsu perform the same thinking state differently", () => {
  const younghee = new NaturalPostureController("younghee", () => 0.05);
  const cheolsu = new NaturalPostureController("cheolsu", () => 0.05);
  younghee.reset(0);
  cheolsu.reset(0);

  let youngheeFrame;
  let cheolsuFrame;
  for (let index = 0; index < 240; index += 1) {
    const elapsed = index / 60;
    youngheeFrame = younghee.update(1 / 60, elapsed, "thinking");
    cheolsuFrame = cheolsu.update(1 / 60, elapsed, "thinking");
  }

  assert.match(younghee.currentVariantId, /^younghee\.thinking\./);
  assert.match(cheolsu.currentVariantId, /^cheolsu\.thinking\./);
  assert.notDeepEqual(youngheeFrame.rightLowerArm, cheolsuFrame.rightLowerArm);
  assert.notDeepEqual(youngheeFrame.head, cheolsuFrame.head);
});

test("persistent thinking rotates among variants without immediately repeating", () => {
  const posture = new NaturalPostureController(
    "younghee",
    sequence([0.05, 0.0, 0.95, 0.0, 0.55, 0.0]),
  );
  posture.reset(0);

  posture.update(1 / 60, 0, "thinking");
  const first = posture.currentVariantId;
  posture.update(1 / 60, 10, "thinking");
  const second = posture.currentVariantId;
  posture.update(1 / 60, 20, "thinking");
  const third = posture.currentVariantId;

  assert.notEqual(first, null);
  assert.notEqual(second, null);
  assert.notEqual(third, null);
  assert.notEqual(first, second);
  assert.notEqual(second, third);
});

test("listening settles into an attentive asymmetric pose", () => {
  const posture = new NaturalPostureController("younghee", sequence([1, 0, 1, 0]));
  posture.reset(0);
  let frame;
  for (let index = 0; index < 600; index += 1) {
    frame = posture.update(1 / 60, index / 60, "listening");
  }

  assert.ok(frame.chest[0] < 0);
  assert.notEqual(frame.leftLowerArm[0], frame.rightLowerArm[0]);
  assert.notEqual(frame.leftShoulder[2], -frame.rightShoulder[2]);
});

test("state and variant changes ease rather than snap", () => {
  const posture = new NaturalPostureController("cheolsu", () => 0.5);
  posture.reset(0);
  for (let index = 0; index < 180; index += 1) {
    posture.update(1 / 60, index / 60, "sleeping");
  }
  const before = posture.update(1 / 60, 3.01, "sleeping");
  const firstThinking = posture.update(1 / 60, 3.02, "thinking");

  assert.ok(Math.abs(firstThinking.head[0] - before.head[0]) < 0.02);
  assert.ok(Math.abs(firstThinking.rightLowerArm[0] - before.rightLowerArm[0]) < 0.04);
});

test("unknown character profile remains a safe generic posture", () => {
  const posture = new NaturalPostureController(null, () => 0.5);
  posture.reset(0);
  let frame;
  for (let index = 0; index < 300; index += 1) {
    frame = posture.update(1 / 60, index / 60, "engaged");
  }
  assert.equal(posture.currentVariantId, null);
  for (const rotation of Object.values(frame)) {
    assert.ok(maxAbs(rotation) <= 0.12);
  }
});
