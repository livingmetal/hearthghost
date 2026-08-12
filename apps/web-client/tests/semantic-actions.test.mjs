import assert from "node:assert/strict";
import test from "node:test";

import { parseCharacterSemanticEvent } from "../.test-dist/character/semantic.js";

for (const gesture of ["clap", "shrug", "stretch"]) {
  test(`${gesture} is accepted only as a parameter-free semantic action`, () => {
    assert.deepEqual(
      parseCharacterSemanticEvent({
        type: "character.gesture",
        payload: { gesture },
      }),
      {
        type: "character.gesture",
        payload: { gesture },
      },
    );

    for (const extra of [
      { count: 100 },
      { speed: 999 },
      { bone: "rightUpperArm" },
      { angle: 3.14 },
    ]) {
      assert.throws(() => parseCharacterSemanticEvent({
        type: "character.gesture",
        payload: { gesture, ...extra },
      }));
    }
  });
}
