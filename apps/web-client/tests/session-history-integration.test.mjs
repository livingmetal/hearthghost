import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const mainSource = await readFile(new URL("../src/main.ts", import.meta.url), "utf8");
const historySource = await readFile(new URL("../src/conversation/history.ts", import.meta.url), "utf8");


test("session history records only successful final text paths", () => {
  assert.match(mainSource, /appendHistory\("user", submittedText\)/);
  assert.match(mainSource, /appendHistory\("assistant", reply\)/);
  assert.match(mainSource, /appendHistory\("user", event\.text\.trim\(\)\)/);
  assert.doesNotMatch(mainSource, /partialTranscript/);
  assert.doesNotMatch(mainSource, /rawAudio/);
});

test("session history clears across attention and app lifecycle boundaries", () => {
  const clearCalls = mainSource.match(/clearSessionHistory\(\)/g) ?? [];
  assert.ok(clearCalls.length >= 4);
  assert.match(mainSource, /attention\.expireIfIdle\(\)[\s\S]*clearSessionHistory\(\)/);
  assert.match(mainSource, /visibilityState === "hidden"[\s\S]*clearSessionHistory\(\)/);
  assert.match(mainSource, /pagehide[\s\S]*clearSessionHistory\(\)/);
  assert.match(mainSource, /data-connect[\s\S]*clearSessionHistory\(\)/);
});

test("session history implementation has no browser persistence calls", () => {
  for (const source of [mainSource, historySource]) {
    assert.doesNotMatch(source, /localStorage/);
    assert.doesNotMatch(source, /sessionStorage/);
    assert.doesNotMatch(source, /indexedDB/);
  }
});

test("history renderer inserts conversation text through textContent", () => {
  assert.match(historySource, /text\.textContent = entry\.text/);
  assert.doesNotMatch(historySource, /innerHTML = entry\.text/);
});
