import assert from "node:assert/strict";
import test from "node:test";

import {
  INITIAL_PRESENTATION,
  parseCharacterSemanticEvent,
  reduceCharacterPresentation,
} from "../.test-dist/character/semantic.js";
import { CharacterViewport } from "../.test-dist/character/viewport.js";

class RecordingRenderer {
  presentations = [];

  async mount() {}
  resize() {}
  present(presentation) {
    this.presentations.push(presentation);
  }
  suspend() {}
  resume() {}
  dispose() {}
}

function fakeElement() {
  return {
    getBoundingClientRect() {
      return { width: 320, height: 480 };
    },
  };
}

test("state and emotion remain separate semantic dimensions", () => {
  const speaking = reduceCharacterPresentation(
    INITIAL_PRESENTATION,
    parseCharacterSemanticEvent({
      type: "character.state",
      payload: { state: "speaking" },
    }),
  );
  const amused = reduceCharacterPresentation(
    speaking,
    parseCharacterSemanticEvent({
      type: "character.emotion",
      payload: { emotion: "amused" },
    }),
  );

  assert.deepEqual(amused, { state: "speaking", emotion: "amused" });
});

test("renderer receives semantic presentation only", async () => {
  const renderer = new RecordingRenderer();
  const viewport = new CharacterViewport(fakeElement(), renderer);
  await viewport.mount();

  viewport.present({ type: "character.state", payload: { state: "thinking" } });

  assert.deepEqual(renderer.presentations.at(-1), {
    state: "thinking",
    emotion: "neutral",
  });
  assert.deepEqual(Object.keys(renderer.presentations.at(-1)).sort(), [
    "emotion",
    "state",
  ]);
});

test("renderer-specific commands are rejected at the viewport boundary", async () => {
  const renderer = new RecordingRenderer();
  const viewport = new CharacterViewport(fakeElement(), renderer);
  await viewport.mount();

  assert.throws(
    () => viewport.present({
      type: "character.state",
      payload: { state: "speaking", blendshape: "Fcl_MTH_A" },
    }),
    /malformed semantic character event/,
  );
  assert.equal(renderer.presentations.length, 1);
});

test("unknown or combined state values fail closed", () => {
  for (const event of [
    { type: "character.state", payload: { state: "speaking_happy" } },
    { type: "character.emotion", payload: { emotion: "execute_tool" } },
    { type: "character.animation", payload: { clip: "wave" } },
  ]) {
    assert.throws(() => parseCharacterSemanticEvent(event));
  }
});
