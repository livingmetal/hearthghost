import assert from "node:assert/strict";
import test from "node:test";

import {
  CHARACTER_EMOTIONS,
  parseCharacterSemanticEvent,
} from "../.test-dist/character/semantic.js";

test("expanded emotion vocabulary remains semantic and renderer agnostic", () => {
  assert.deepEqual(CHARACTER_EMOTIONS, [
    "neutral",
    "happy",
    "amused",
    "curious",
    "concerned",
    "surprised",
    "angry",
    "sad",
    "annoyed",
    "embarrassed",
    "smug",
    "affectionate",
  ]);

  for (const emotion of CHARACTER_EMOTIONS) {
    assert.deepEqual(
      parseCharacterSemanticEvent({
        type: "character.emotion",
        payload: { emotion },
      }),
      {
        type: "character.emotion",
        payload: { emotion },
      },
    );
  }
});

test("emotion events cannot inject expression styles or morph weights", () => {
  for (const payload of [
    { emotion: "smug", style: "mesugaki" },
    { emotion: "embarrassed", style: "tsundere" },
    { emotion: "affectionate", style: "yandere" },
    { emotion: "happy", happy: 1 },
    { emotion: "smug", smirk: 0.9 },
    { emotion: "sad", blink: 1 },
    { emotion: "angry", bone: "head" },
  ]) {
    assert.throws(() => parseCharacterSemanticEvent({
      type: "character.emotion",
      payload,
    }));
  }
});
