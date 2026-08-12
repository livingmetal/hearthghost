import assert from "node:assert/strict";
import test from "node:test";

import { actionMotionFrame } from "../.test-dist/character/vrm-action-motion.js";

function maxAbs(frame) {
  return Math.max(
    ...Object.values(frame.rotations).flatMap((rotation) => rotation.map((value) => Math.abs(value))),
  );
}

test("clap prepares both open hands and returns cleanly to rest", () => {
  const start = actionMotionFrame({ gesture: "clap" }, 0, "younghee");
  const middle = actionMotionFrame({ gesture: "clap" }, 0.50, "younghee");
  const end = actionMotionFrame({ gesture: "clap" }, 1, "younghee");

  assert.ok(maxAbs(start) < 0.001);
  assert.ok(middle.leftHandOpen > 0.95);
  assert.ok(middle.rightHandOpen > 0.95);
  assert.ok(Math.abs(middle.rotations.leftLowerArm[0]) > 0.5);
  assert.ok(maxAbs(end) < 0.001);
});

test("clap contains repeated approach and release phases", () => {
  const samples = [];
  for (let index = 15; index <= 85; index += 5) {
    const frame = actionMotionFrame({ gesture: "clap" }, index / 100, "younghee");
    samples.push(frame.rotations.leftHand[1]);
  }

  let directionChanges = 0;
  let lastDirection = 0;
  for (let index = 1; index < samples.length; index += 1) {
    const delta = samples[index] - samples[index - 1];
    const direction = Math.sign(delta);
    if (direction !== 0 && lastDirection !== 0 && direction !== lastDirection) {
      directionChanges += 1;
    }
    if (direction !== 0) {
      lastDirection = direction;
    }
  }
  assert.ok(directionChanges >= 4);
});

test("shrug lifts both shoulders and opens both palms", () => {
  const frame = actionMotionFrame({ gesture: "shrug" }, 0.5, "younghee");

  assert.ok(frame.rotations.leftShoulder[0] < -0.07);
  assert.ok(frame.rotations.rightShoulder[0] < -0.07);
  assert.ok(frame.rotations.leftShoulder[2] < 0);
  assert.ok(frame.rotations.rightShoulder[2] > 0);
  assert.ok(frame.leftHandOpen > 0.9);
  assert.ok(frame.rightHandOpen > 0.9);
});

test("stretch raises both arms symmetrically while opening the chest", () => {
  const frame = actionMotionFrame({ gesture: "stretch" }, 0.5, "younghee");

  assert.ok(frame.rotations.chest[0] < -0.07);
  assert.ok(frame.rotations.leftUpperArm[2] < -0.7);
  assert.ok(frame.rotations.rightUpperArm[2] > 0.7);
  assert.ok(frame.leftHandOpen > 0.9);
  assert.ok(frame.rightHandOpen > 0.9);
});

test("cheolsu action performance remains more restrained than younghee", () => {
  const y = actionMotionFrame({ gesture: "stretch" }, 0.5, "younghee");
  const c = actionMotionFrame({ gesture: "stretch" }, 0.5, "cheolsu");

  assert.ok(Math.abs(c.rotations.leftUpperArm[2]) < Math.abs(y.rotations.leftUpperArm[2]));
  assert.ok(Math.abs(c.rotations.chest[0]) < Math.abs(y.rotations.chest[0]));
});

test("all new actions remain bounded and never expose root movement", () => {
  for (const character of ["younghee", "cheolsu"]) {
    for (const gesture of ["clap", "shrug", "stretch"]) {
      for (let index = 0; index <= 100; index += 1) {
        const frame = actionMotionFrame({ gesture }, index / 100, character);
        assert.ok(maxAbs(frame) <= 0.90);
        assert.equal("position" in frame, false);
        assert.equal("rootX" in frame, false);
        assert.equal("rootZ" in frame, false);
      }
    }
  }
});
