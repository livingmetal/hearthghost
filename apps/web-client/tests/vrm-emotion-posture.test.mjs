import assert from "node:assert/strict";
import test from "node:test";

import { EmotionPostureController } from "../.test-dist/character/vrm-emotion-posture.js";

function settle(controller, state, emotion, seconds = 2) {
  let frame;
  const frames = Math.ceil(seconds * 60);
  for (let index = 0; index < frames; index += 1) {
    frame = controller.update(1 / 60, state, emotion);
  }
  return frame;
}

function maxAbs(frame) {
  return Math.max(
    ...Object.values(frame).flatMap((rotation) => rotation.map((value) => Math.abs(value))),
  );
}

test("neutral and sleeping emotion overlays do not create body language", () => {
  const controller = new EmotionPostureController("younghee");
  controller.reset();

  const neutral = settle(controller, "engaged", "neutral");
  assert.equal(maxAbs(neutral), 0);

  const sleeping = settle(controller, "sleeping", "surprised");
  assert.ok(maxAbs(sleeping) < 0.0005);
});

test("curious leans toward the conversation and tilts the head", () => {
  const controller = new EmotionPostureController("younghee");
  controller.reset();
  const frame = settle(controller, "listening", "curious");

  assert.ok(frame.chest[0] < -0.008);
  assert.ok(Math.abs(frame.head[2]) > 0.015);
  assert.ok(Math.abs(frame.head[1]) > 0.007);
});

test("concerned closes the shoulders and lowers the head", () => {
  const controller = new EmotionPostureController("younghee");
  controller.reset();
  const frame = settle(controller, "listening", "concerned");

  assert.ok(frame.head[0] > 0.008);
  assert.ok(frame.leftShoulder[2] > 0);
  assert.ok(frame.rightShoulder[2] < 0);
});

test("happy opens the silhouette without large joint rotations", () => {
  const controller = new EmotionPostureController("younghee");
  controller.reset();
  const frame = settle(controller, "speaking", "happy");

  assert.ok(frame.leftShoulder[2] < 0);
  assert.ok(frame.rightShoulder[2] > 0);
  assert.ok(maxAbs(frame) < 0.06);
});

test("surprise reacts faster in noticing but remains conservative", () => {
  const controller = new EmotionPostureController("younghee");
  controller.reset();
  const first = controller.update(1 / 60, "noticing", "surprised");
  const firstChest = first.chest[0];
  const settled = settle(controller, "noticing", "surprised", 1.5);

  assert.ok(Math.abs(firstChest) > 0);
  assert.ok(settled.chest[0] > firstChest);
  assert.ok(maxAbs(settled) < 0.08);
});

test("younghee and cheolsu express amusement with different scale and lateral bias", () => {
  const younghee = new EmotionPostureController("younghee");
  const cheolsu = new EmotionPostureController("cheolsu");
  younghee.reset();
  cheolsu.reset();

  const y = settle(younghee, "engaged", "amused");
  const c = settle(cheolsu, "engaged", "amused");

  assert.ok(Math.abs(y.head[2]) > Math.abs(c.head[2]));
  assert.equal(Math.sign(y.head[2]), -Math.sign(c.head[2]));
});

test("emotion transitions ease instead of snapping", () => {
  const controller = new EmotionPostureController("younghee");
  controller.reset();
  const before = settle(controller, "listening", "concerned");
  const beforeHead = before.head[0];
  const beforeShoulder = before.leftShoulder[2];
  const next = controller.update(1 / 60, "listening", "happy");

  assert.ok(Math.abs(next.head[0] - beforeHead) < 0.01);
  assert.ok(Math.abs(next.leftShoulder[2] - beforeShoulder) < 0.01);
});
