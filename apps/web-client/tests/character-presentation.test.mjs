import assert from "node:assert/strict";
import test from "node:test";

import { CharacterExperienceController } from "../.test-dist/character/experience.js";
import {
  INITIAL_PRESENTATION,
  parseCharacterSemanticEvent,
  reduceCharacterPresentation,
} from "../.test-dist/character/semantic.js";
import { CharacterViewport } from "../.test-dist/character/viewport.js";
import {
  VRM_CAMERA_FRAMING,
  cameraClearanceAtForwardExtent,
} from "../.test-dist/character/vrm-framing.js";
import {
  MAX_CAMERA_Z,
  MIN_CAMERA_Z,
  VrmViewManipulation,
} from "../.test-dist/character/vrm-view-manipulation.js";

class RecordingRenderer {
  presentations = [];
  gestures = [];

  async mount() {}
  resize() {}
  present(presentation) {
    this.presentations.push(presentation);
  }
  performGesture(gesture) {
    this.gestures.push(gesture);
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

async function experienceFixture() {
  const renderer = new RecordingRenderer();
  const viewport = new CharacterViewport(fakeElement(), renderer);
  await viewport.mount();
  return {
    renderer,
    viewport,
    experience: new CharacterExperienceController(viewport),
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

test("VRM conversation framing is close while preserving forward gesture clearance", () => {
  assert.ok(VRM_CAMERA_FRAMING.cameraZ < 3);
  assert.ok(VRM_CAMERA_FRAMING.cameraZ > 2.4);
  assert.ok(cameraClearanceAtForwardExtent() >= 2.2);
  assert.equal(VRM_CAMERA_FRAMING.lookAtTargetZ, VRM_CAMERA_FRAMING.cameraZ);
});

test("VRM view drag, wheel, pinch and reset stay local and bounded", () => {
  const view = new VrmViewManipulation();

  view.beginPointer(1, 100, 100);
  const dragged = view.movePointer(1, 180, 140, 400, 500);
  assert.ok(dragged.offsetX > 0);
  assert.ok(dragged.offsetY < 0);
  view.endPointer(1);

  const zoomedIn = view.zoomByWheel(-10_000);
  assert.equal(MIN_CAMERA_Z, 1.05);
  assert.equal(zoomedIn.cameraZ, MIN_CAMERA_Z);
  const zoomedOut = view.zoomByWheel(10_000);
  assert.equal(zoomedOut.cameraZ, MAX_CAMERA_Z);

  view.reset();
  view.zoomByWheel(-10_000);
  view.beginPointer(3, 100, 100);
  const closeDragged = view.movePointer(3, 180, 140, 400, 500);
  assert.ok(closeDragged.offsetX > 0);
  assert.ok(closeDragged.offsetX < dragged.offsetX);
  view.endPointer(3);

  view.reset();
  view.beginPointer(1, 100, 100);
  view.beginPointer(2, 200, 100);
  const pinched = view.movePointer(2, 1_000, 100, 400, 500);
  assert.equal(pinched.cameraZ, MIN_CAMERA_Z);

  assert.deepEqual(view.reset(), {
    offsetX: 0,
    offsetY: 0,
    cameraZ: VRM_CAMERA_FRAMING.cameraZ,
  });
});

test("noticing is a first-class semantic state", () => {
  const noticing = reduceCharacterPresentation(
    INITIAL_PRESENTATION,
    parseCharacterSemanticEvent({
      type: "character.state",
      payload: { state: "noticing" },
    }),
  );
  assert.deepEqual(noticing, { state: "noticing", emotion: "neutral" });
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

test("safe semantic gestures reach the renderer without changing presentation", async () => {
  const { renderer, viewport, experience } = await experienceFixture();
  const before = viewport.snapshot();

  experience.performGesture({ gesture: "wave", side: "right" });
  experience.performGesture({ gesture: "turn", direction: "left" });
  experience.performGesture({ gesture: "move", direction: "forward" });

  assert.deepEqual(renderer.gestures, [
    { gesture: "wave", side: "right" },
    { gesture: "turn", direction: "left" },
    { gesture: "move", direction: "forward" },
  ]);
  assert.deepEqual(viewport.snapshot(), before);
});

test("gesture payloads reject arbitrary renderer or bone parameters", () => {
  for (const event of [
    {
      type: "character.gesture",
      payload: { gesture: "wave", side: "right", bone: "rightUpperArm" },
    },
    {
      type: "character.gesture",
      payload: { gesture: "turn", direction: "clockwise" },
    },
    {
      type: "character.gesture",
      payload: { gesture: "move", direction: "forward", distance: 100 },
    },
    {
      type: "character.gesture",
      payload: { gesture: "move", direction: "up" },
    },
    {
      type: "character.gesture",
      payload: { gesture: "run_shell_command" },
    },
  ]) {
    assert.throws(() => parseCharacterSemanticEvent(event));
  }
});

test("touch wake and local voice phases produce visible character states", async () => {
  const { viewport, experience } = await experienceFixture();

  experience.wakeByTouch();
  assert.deepEqual(viewport.snapshot(), { state: "noticing", emotion: "curious" });

  experience.beginListening();
  assert.deepEqual(viewport.snapshot(), { state: "listening", emotion: "curious" });

  experience.beginThinking();
  assert.deepEqual(viewport.snapshot(), { state: "thinking", emotion: "neutral" });

  experience.beginSpeaking();
  assert.deepEqual(viewport.snapshot(), { state: "speaking", emotion: "neutral" });

  experience.engage();
  assert.deepEqual(viewport.snapshot(), { state: "engaged", emotion: "neutral" });

  experience.sleep();
  assert.deepEqual(viewport.snapshot(), { state: "sleeping", emotion: "neutral" });
});

test("success and error cues change emotion without inventing device authority", async () => {
  const { viewport, experience } = await experienceFixture();
  experience.wakeByTouch();
  experience.acknowledgeSuccess();
  assert.deepEqual(viewport.snapshot(), { state: "engaged", emotion: "happy" });

  experience.showConcern();
  assert.deepEqual(viewport.snapshot(), { state: "engaged", emotion: "concerned" });
});

test("server semantic events still pass through the same strict viewport boundary", async () => {
  const { renderer, viewport, experience } = await experienceFixture();
  experience.presentServerEvent({
    type: "character.state",
    payload: { state: "thinking" },
  });
  assert.equal(viewport.snapshot().state, "thinking");

  experience.presentServerEvent({
    type: "character.gesture",
    payload: { gesture: "nod" },
  });
  assert.deepEqual(renderer.gestures.at(-1), { gesture: "nod" });

  assert.throws(() => experience.presentServerEvent({
    type: "character.animation",
    payload: { clip: "run-shell-command" },
  }));
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
