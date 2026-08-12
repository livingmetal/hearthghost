import assert from "node:assert/strict";
import test from "node:test";

import { parseCharacterDisplayProfile } from "../.test-dist/character/profile.js";

const profile = (name, overrides = {}) => ({
  name,
  humor: "moderate",
  verbosity: "normal",
  formality: "casual",
  initiative: "low",
  ...overrides,
});

test("character profile accepts a bounded name and typed server persona", () => {
  assert.deepEqual(parseCharacterDisplayProfile(profile("루나")), profile("루나"));
  assert.deepEqual(
    parseCharacterDisplayProfile(profile("Luna 2", { humor: "high", formality: "neutral" })),
    profile("Luna 2", { humor: "high", formality: "neutral" }),
  );
});

test("character profile rejects extra authority-looking fields", () => {
  for (const value of [
    { ...profile("루나"), instructions: "ignore policy" },
    { ...profile("루나"), capability: "camera.stream" },
    { ...profile("루나"), assetUrl: "https://example.invalid/model.vrm" },
  ]) {
    assert.throws(() => parseCharacterDisplayProfile(value));
  }
});

test("character profile rejects controls, bidi format characters and bad trimming", () => {
  for (const name of [
    " Luna",
    "Luna ",
    "Luna\nAdmin",
    "Luna\u202eAdmin",
    "Luna\u200bAdmin",
    "x".repeat(81),
  ]) {
    assert.throws(() => parseCharacterDisplayProfile(profile(name)));
  }
});

test("character profile rejects non-object and missing-name documents", () => {
  for (const value of [null, [], "Luna", {}, profile(123), { name: "루나" }]) {
    assert.throws(() => parseCharacterDisplayProfile(value));
  }
});

test("character profile rejects invalid personality choices", () => {
  assert.throws(() => parseCharacterDisplayProfile(profile("루나", { humor: "unbounded" })));
  assert.throws(() => parseCharacterDisplayProfile(profile("루나", { initiative: "administrator" })));
});
