import assert from "node:assert/strict";
import test from "node:test";

import { GazeBehaviorController } from "../.test-dist/character/vrm-gaze-behavior.js";

function sequence(values) {
  let index = 0;
  return () => values[index++ % values.length];
}

function settle(controller, elapsedStart, state, emotion, seconds = 1.5) {
  let frame;
  const frames = Math.ceil(seconds * 60);
  for (let index = 0; index < frames; index += 1) {
    frame = controller.update(1 / 60, elapsedStart + index / 60, state, emotion);
  }
  return frame;
}

test("sleeping gaze settles down and never invents a glance", () => {
  const gaze = new GazeBehaviorController("younghee", () => 0.5);
  gaze.reset(0);
  const frame = settle(gaze, 0, "sleeping", "neutral");

  assert.equal(frame.behavior, "focus");
  assert.ok(Math.abs(frame.x) < 0.001);
  assert.ok(frame.y < 1.31);
});

test("noticing and surprise snap attention back toward the user", () => {
  const gaze = new GazeBehaviorController("younghee", sequence([0.1, 0.9, 0.2, 0.8]));
  gaze.reset(0);
  settle(gaze, 0, "thinking", "neutral", 1.0);

  const noticing = settle(gaze, 1.1, "noticing", "surprised", 0.7);
  assert.equal(noticing.behavior, "focus");
  assert.ok(Math.abs(noticing.x) < 0.02);
  assert.ok(Math.abs(noticing.y - 1.48) < 0.02);
});

test("thinking uses deliberate glance variants instead of one hard-coded side", () => {
  const gaze = new GazeBehaviorController(
    "younghee",
    sequence([0.50, 0.10, 0.20, 0.60, 0.90, 0.20, 0.90, 0.30]),
  );
  gaze.reset(0);

  let frame = gaze.update(1 / 60, 0, "thinking", "neutral");
  const firstBehavior = frame.behavior;
  frame = gaze.update(1 / 60, 4, "thinking", "neutral");
  frame = gaze.update(1 / 60, 8, "thinking", "neutral");
  const laterBehavior = frame.behavior;

  assert.match(firstBehavior, /^glance-/);
  assert.match(laterBehavior, /^glance-/);
  assert.notEqual(firstBehavior, "focus");
  assert.ok(Math.abs(frame.x) <= 0.30);
  assert.ok(frame.y >= 1.30 && frame.y <= 1.64);
});

test("an ambient glance returns to user focus before another large glance", () => {
  const gaze = new GazeBehaviorController(
    "younghee",
    sequence([0.0, 0.0, 0.0, 0.1, 0.3, 0.7, 0.4, 0.6]),
  );
  gaze.reset(0);
  settle(gaze, 0, "engaged", "neutral", 0.5);

  let frame = gaze.update(1 / 60, 10, "engaged", "neutral");
  assert.match(frame.behavior, /^glance-/);

  frame = settle(gaze, 12, "engaged", "neutral", 0.7);
  assert.equal(frame.behavior, "focus");
  assert.ok(Math.abs(frame.x) < 0.05);
});

test("concerned thinking favors a downward gaze", () => {
  const gaze = new GazeBehaviorController("cheolsu", sequence([0.10, 0.50, 0.40]));
  gaze.reset(0);
  const frame = settle(gaze, 0, "thinking", "concerned", 1.0);

  assert.equal(frame.behavior, "glance-down");
  assert.ok(frame.y < 1.43);
});

test("younghee gaze amplitude is larger than cheolsu for the same side glance", () => {
  const randomY = sequence([0.60, 0.80, 0.20, 0.50]);
  const randomC = sequence([0.60, 0.80, 0.20, 0.50]);
  const younghee = new GazeBehaviorController("younghee", randomY);
  const cheolsu = new GazeBehaviorController("cheolsu", randomC);
  younghee.reset(0);
  cheolsu.reset(0);

  const y = settle(younghee, 0, "thinking", "neutral", 1.2);
  const c = settle(cheolsu, 0, "thinking", "neutral", 1.2);

  assert.ok(Math.abs(y.x) > Math.abs(c.x));
  assert.ok(Math.abs(y.x) <= 0.30);
  assert.ok(Math.abs(c.x) <= 0.30);
});

test("gaze transitions remain bounded under repeated long-running updates", () => {
  const gaze = new GazeBehaviorController(
    "younghee",
    sequence([0.02, 0.98, 0.15, 0.85, 0.25, 0.75, 0.35, 0.65]),
  );
  gaze.reset(0);

  for (let index = 0; index < 3600; index += 1) {
    const frame = gaze.update(1 / 60, index / 60, "engaged", "amused");
    assert.ok(frame.x >= -0.30 && frame.x <= 0.30);
    assert.ok(frame.y >= 1.28 && frame.y <= 1.64);
  }
});
