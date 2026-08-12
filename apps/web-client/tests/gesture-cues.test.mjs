import assert from "node:assert/strict";
import test from "node:test";

import { inferCharacterGestures } from "../.test-dist/character/gesture-cues.js";

test("left hand raise is mapped to a semantic gesture", () => {
  assert.deepEqual(inferCharacterGestures("왼손을 들어봐"), [
    { gesture: "raise_hand", side: "left" },
  ]);
});

test("right full turn is mapped without renderer-specific instructions", () => {
  assert.deepEqual(inferCharacterGestures("오른쪽으로 한 바퀴 돌아봐"), [
    { gesture: "turn", direction: "right" },
  ]);
});

test("assistant stage direction can trigger a wave", () => {
  assert.deepEqual(inferCharacterGestures("*철수가 가볍게 손을 흔든다.* 👋"), [
    { gesture: "wave", side: "right" },
  ]);
});

test("head gestures and bow are recognized", () => {
  assert.deepEqual(inferCharacterGestures("고개를 끄덕이고 허리를 숙여 인사한다"), [
    { gesture: "nod" },
    { gesture: "bow" },
  ]);
  assert.deepEqual(inferCharacterGestures("고개를 좌우로 흔든다"), [
    { gesture: "shake_head" },
  ]);
});

test("negated motion requests do not animate", () => {
  assert.deepEqual(inferCharacterGestures("손 흔들지 마"), []);
  assert.deepEqual(inferCharacterGestures("오른쪽으로 돌지 말고 가만히 있어"), []);
});
