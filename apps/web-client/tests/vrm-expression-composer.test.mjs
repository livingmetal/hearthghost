import assert from "node:assert/strict";
import test from "node:test";

import { CHARACTER_EMOTIONS } from "../.test-dist/character/semantic.js";
import {
  EXPRESSION_STYLE_IDS,
  VrmExpressionComposer,
  composeExpressionTarget,
  defaultExpressionStyleForCharacter,
} from "../.test-dist/character/vrm-expression-composer.js";

const STANDARD = [
  "happy",
  "angry",
  "sad",
  "relaxed",
  "surprised",
  "blink",
  "blinkLeft",
  "blinkRight",
  "lookUp",
  "lookDown",
  "lookLeft",
  "lookRight",
  "aa",
  "ih",
  "ou",
  "ee",
  "oh",
];

const WITH_CUSTOM = [
  ...STANDARD,
  "smirk",
  "blush",
  "annoyed",
  "affection",
];

test("character defaults select presentation style without changing semantic emotion", () => {
  assert.equal(defaultExpressionStyleForCharacter("younghee"), "playful");
  assert.equal(defaultExpressionStyleForCharacter("cheolsu"), "reserved");
  assert.equal(defaultExpressionStyleForCharacter(null), "balanced");
  assert.deepEqual(EXPRESSION_STYLE_IDS, [
    "balanced",
    "playful",
    "reserved",
    "tsundere",
    "mesugaki",
    "yandere",
  ]);
});

test("all semantic emotions have bounded standard-expression fallbacks", () => {
  for (const emotion of CHARACTER_EMOTIONS) {
    const target = composeExpressionTarget(emotion, "balanced", STANDARD);
    for (const [name, value] of Object.entries(target)) {
      assert.ok(STANDARD.map((candidate) => candidate.toLowerCase()).includes(name));
      assert.ok(value >= 0 && value <= 1, `${emotion}/${name} escaped expression bounds`);
    }
    if (emotion !== "neutral") {
      assert.ok(Object.keys(target).length > 0, `${emotion} has no standard fallback`);
    }
  }
});

test("composer never takes ownership of blink gaze or lip-sync channels", () => {
  const target = composeExpressionTarget("affectionate", "yandere", WITH_CUSTOM);
  for (const reserved of [
    "blink",
    "blinkleft",
    "blinkright",
    "lookup",
    "lookdown",
    "lookleft",
    "lookright",
    "aa",
    "ih",
    "ou",
    "ee",
    "oh",
  ]) {
    assert.equal(Object.hasOwn(target, reserved), false, reserved);
  }
});

test("custom expressions enrich a recipe but missing custom channels fail soft", () => {
  const plain = composeExpressionTarget("smug", "mesugaki", STANDARD);
  const custom = composeExpressionTarget("smug", "mesugaki", WITH_CUSTOM);

  assert.equal(Object.hasOwn(plain, "smirk"), false);
  assert.ok((plain.happy ?? 0) > 0);
  assert.ok((custom.smirk ?? 0) > 0.5);
  assert.ok((custom.happy ?? 0) > 0);
});

test("archetype styles alter expression recipes rather than semantic labels", () => {
  const balancedEmbarrassed = composeExpressionTarget("embarrassed", "balanced", WITH_CUSTOM);
  const tsundereEmbarrassed = composeExpressionTarget("embarrassed", "tsundere", WITH_CUSTOM);
  assert.ok((tsundereEmbarrassed.angry ?? 0) > (balancedEmbarrassed.angry ?? 0));
  assert.ok((tsundereEmbarrassed.blush ?? 0) > (balancedEmbarrassed.blush ?? 0));

  const balancedSmug = composeExpressionTarget("smug", "balanced", WITH_CUSTOM);
  const mesugakiSmug = composeExpressionTarget("smug", "mesugaki", WITH_CUSTOM);
  assert.ok((mesugakiSmug.smirk ?? 0) > (balancedSmug.smirk ?? 0));

  const balancedAffection = composeExpressionTarget("affectionate", "balanced", WITH_CUSTOM);
  const yandereAffection = composeExpressionTarget("affectionate", "yandere", WITH_CUSTOM);
  assert.ok((yandereAffection.relaxed ?? 0) > (balancedAffection.relaxed ?? 0));
  assert.ok((yandereAffection.affection ?? 0) > (balancedAffection.affection ?? 0));
});

test("reserved character style remains less intense than playful for the same smile", () => {
  const playful = composeExpressionTarget("happy", "playful", STANDARD);
  const reserved = composeExpressionTarget("happy", "reserved", STANDARD);
  assert.ok((playful.happy ?? 0) > (reserved.happy ?? 0));
});

test("runtime composer eases toward targets and sleeping releases the face", () => {
  const composer = new VrmExpressionComposer("younghee");
  composer.setCapabilities(WITH_CUSTOM);

  const first = composer.update(0.016, "speaking", "smug");
  const firstHappy = first.get("happy") ?? 0;
  assert.ok(firstHappy > 0);
  assert.ok(firstHappy < (composeExpressionTarget("smug", "playful", WITH_CUSTOM).happy ?? 1));

  for (let index = 0; index < 120; index += 1) {
    composer.update(1 / 60, "speaking", "smug");
  }
  const settled = composer.update(1 / 60, "speaking", "smug");
  assert.ok((settled.get("happy") ?? 0) > firstHappy);

  for (let index = 0; index < 180; index += 1) {
    composer.update(1 / 60, "sleeping", "neutral");
  }
  const sleeping = composer.update(1 / 60, "sleeping", "neutral");
  for (const value of sleeping.values()) {
    assert.ok(value < 0.001);
  }
});

test("style can be swapped locally without exposing morph weights to semantic events", () => {
  const composer = new VrmExpressionComposer(null, "balanced");
  composer.setCapabilities(WITH_CUSTOM);
  assert.equal(composer.getStyle(), "balanced");
  composer.setStyle("tsundere");
  assert.equal(composer.getStyle(), "tsundere");
  const frame = composer.update(0.1, "engaged", "embarrassed");
  assert.ok((frame.get("angry") ?? 0) > 0);
  assert.ok((frame.get("blush") ?? 0) > 0);
});
