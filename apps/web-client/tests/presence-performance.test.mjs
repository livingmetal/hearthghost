import assert from "node:assert/strict";
import test from "node:test";

import {
  characterIdFromViewportLabel,
  exitPreludeGestureFor,
  presenceMotionFor,
} from "../.test-dist/character/presence-performance.js";

test("presence labels resolve only known bundled characters", () => {
  assert.equal(characterIdFromViewportLabel("영희 character viewport"), "younghee");
  assert.equal(characterIdFromViewportLabel("철수 character viewport"), "cheolsu");
  assert.equal(characterIdFromViewportLabel("Luna character viewport"), null);
});

test("Younghee alternates a peek entrance with a softer side entrance", () => {
  const peek = presenceMotionFor("younghee", "enter", 0);
  const soft = presenceMotionFor("younghee", "enter", 1);
  const wrapped = presenceMotionFor("younghee", "enter", 2);

  assert.equal(peek.id, "younghee.enter.peek-left");
  assert.equal(soft.id, "younghee.enter.soft-left");
  assert.equal(wrapped.id, peek.id);
  assert.ok(peek.keyframes.length >= 4);
  assert.match(peek.keyframes[0].transform, /-72%/);
  assert.equal(peek.keyframes.at(-1).transform, "translate3d(0, 0, 0) scale(1)");
  assert.ok(peek.durationMillis <= 850);
  assert.ok(soft.durationMillis <= 850);
});

test("Cheolsu uses restrained right-side entrance and exit variants", () => {
  const firstEnter = presenceMotionFor("cheolsu", "enter", 0);
  const secondEnter = presenceMotionFor("cheolsu", "enter", 1);
  const exit = presenceMotionFor("cheolsu", "exit", 0);

  assert.notEqual(firstEnter.id, secondEnter.id);
  assert.match(firstEnter.keyframes[0].transform, /44%/);
  assert.match(exit.keyframes.at(-1).transform, /46%/);
  assert.ok(firstEnter.durationMillis <= 850);
  assert.ok(secondEnter.durationMillis <= 850);
  assert.ok(exit.durationMillis <= 650);
});

test("exit preludes are bounded semantic gestures, not renderer commands", () => {
  assert.deepEqual(exitPreludeGestureFor("younghee", 0), { gesture: "wave", side: "right" });
  assert.deepEqual(exitPreludeGestureFor("younghee", 1), { gesture: "nod" });
  assert.deepEqual(exitPreludeGestureFor("cheolsu", 0), { gesture: "nod" });
  assert.equal(exitPreludeGestureFor("cheolsu", 1), null);
  assert.equal(exitPreludeGestureFor(null, 0), null);
});
