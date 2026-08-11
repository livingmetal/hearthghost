import assert from "node:assert/strict";
import test from "node:test";

import { EphemeralSessionHistory } from "../.test-dist/conversation/history.js";


test("session history preserves bounded user and assistant display text", () => {
  const history = new EphemeralSessionHistory();
  history.append("user", "안녕");
  const snapshot = history.append("assistant", "반가워요");
  assert.deepEqual(snapshot, [
    { role: "user", text: "안녕" },
    { role: "assistant", text: "반가워요" },
  ]);
});

test("session history keeps only the most recent twenty entries", () => {
  const history = new EphemeralSessionHistory();
  for (let index = 0; index < 25; index += 1) {
    history.append(index % 2 === 0 ? "user" : "assistant", `entry-${index}`);
  }
  const snapshot = history.snapshot();
  assert.equal(snapshot.length, 20);
  assert.equal(snapshot[0].text, "entry-5");
  assert.equal(snapshot.at(-1).text, "entry-24");
});

test("session history clears without retaining a backing reference", () => {
  const history = new EphemeralSessionHistory();
  const before = history.append("user", "temporary text");
  history.clear();
  assert.deepEqual(history.snapshot(), []);
  assert.deepEqual(before, [{ role: "user", text: "temporary text" }]);
});

test("session history rejects empty nul and oversized display text", () => {
  const history = new EphemeralSessionHistory();
  for (const text of ["", "   ", "bad\u0000text", "x".repeat(4001)]) {
    assert.throws(() => history.append("user", text));
  }
});

test("session history has no persistence API", () => {
  const history = new EphemeralSessionHistory();
  assert.equal("save" in history, false);
  assert.equal("load" in history, false);
  assert.equal("storage" in history, false);
  assert.equal("serialize" in history, false);
});
