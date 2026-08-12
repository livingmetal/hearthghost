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

test("bounded screen-space movement is inferred without coordinates", () => {
  assert.deepEqual(inferCharacterGestures("조금 앞으로 다가와봐"), [
    { gesture: "move", direction: "forward" },
  ]);
  assert.deepEqual(inferCharacterGestures("한 걸음 뒤로 물러나"), [
    { gesture: "move", direction: "backward" },
  ]);
  assert.deepEqual(inferCharacterGestures("화면 왼쪽으로 이동해"), [
    { gesture: "move", direction: "left" },
  ]);
  assert.deepEqual(inferCharacterGestures("move right"), [
    { gesture: "move", direction: "right" },
  ]);
});

test("clap shrug and stretch are inferred as parameter-free semantic actions", () => {
  assert.deepEqual(inferCharacterGestures("박수 쳐봐"), [
    { gesture: "clap" },
  ]);
  assert.deepEqual(inferCharacterGestures("어깨를 으쓱해봐"), [
    { gesture: "shrug" },
  ]);
  assert.deepEqual(inferCharacterGestures("기지개 한번 켜"), [
    { gesture: "stretch" },
  ]);
  assert.deepEqual(inferCharacterGestures("clap and shrug"), [
    { gesture: "clap" },
    { gesture: "shrug" },
  ]);
});

test("negated motion requests do not animate", () => {
  assert.deepEqual(inferCharacterGestures("손 흔들지 마"), []);
  assert.deepEqual(inferCharacterGestures("오른쪽으로 돌지 말고 가만히 있어"), []);
  assert.deepEqual(inferCharacterGestures("앞으로 다가오지 마"), []);
  assert.deepEqual(inferCharacterGestures("박수치지 마"), []);
  assert.deepEqual(inferCharacterGestures("don't shrug"), []);
});
