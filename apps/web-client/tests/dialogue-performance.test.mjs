import assert from "node:assert/strict";
import test from "node:test";

import { planDialoguePerformance } from "../.test-dist/character/dialogue-performance.js";

test("dialogue performance follows emotional sentence changes", () => {
  const plan = planDialoguePerformance("잘했어! 그런데 이 부분은 조금 조심해야 해. 왜 그런지 볼까?");
  assert.equal(plan.beats[0].emotion, "happy");
  assert.ok(plan.beats.some((beat) => beat.emotion === "concerned"));
  assert.ok(plan.beats.some((beat) => beat.emotion === "curious"));
  assert.deepEqual([...plan.beats].map((beat) => beat.offset), [...plan.beats].map((beat) => beat.offset).toSorted((a, b) => a - b));
});

test("celebration may clap but automatic dialogue gestures stay sparse", () => {
  const plan = planDialoguePerformance("축하해, 해냈네! 정말 잘했어. 그래, 다음 단계로 가자.");
  const gestures = plan.beats.flatMap((beat) => beat.gesture === null ? [] : [beat.gesture]);
  assert.deepEqual(gestures, [{ gesture: "clap" }]);
});

test("automatic dialogue performance never invents spatial commands", () => {
  const plan = planDialoguePerformance("좋아! 왼쪽을 보고 앞으로 가는 방법을 설명할게. 어떻게 할지 궁금하지?");
  const gestures = plan.beats.flatMap((beat) => beat.gesture === null ? [] : [beat.gesture.gesture]);
  assert.equal(gestures.some((gesture) => ["move", "turn", "point", "raise_hand", "wave"].includes(gesture)), false);
});

test("embodied acknowledgement does not stack an automatic nod on explicit gestures", () => {
  const plan = planDialoguePerformance("응, 이렇게 할게.");
  assert.equal(plan.beats.some((beat) => beat.gesture !== null), false);
});

test("uncertainty can use a bounded shrug and only once", () => {
  const plan = planDialoguePerformance("확실하지 않지만 한 가지 가능성은 있어. 모르겠으면 확인해보자.");
  const gestures = plan.beats.flatMap((beat) => beat.gesture === null ? [] : [beat.gesture]);
  assert.deepEqual(gestures, [{ gesture: "shrug" }]);
});

test("empty replies produce no performance beats", () => {
  const plan = planDialoguePerformance("   ");
  assert.equal(plan.text, "");
  assert.deepEqual(plan.beats, []);
});
