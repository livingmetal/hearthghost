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

test("point accepts only left or right semantic direction", () => {
  for (const direction of ["left", "right"]) {
    assert.deepEqual(
      parseCharacterSemanticEvent({
        type: "character.gesture",
        payload: { gesture: "point", direction },
      }),
      {
        type: "character.gesture",
        payload: { gesture: "point", direction },
      },
    );
  }

  for (const payload of [
    { gesture: "point" },
    { gesture: "point", direction: "forward" },
    { gesture: "point", direction: "left", angle: 0.5 },
    { gesture: "point", direction: "right", x: 0.8, y: 0.2 },
    { gesture: "point", direction: "right", bone: "rightIndexProximal" },
  ]) {
    assert.throws(() => parseCharacterSemanticEvent({
      type: "character.gesture",
      payload,
    }));
  }
});
