import assert from "node:assert/strict";
import test from "node:test";

import {
  CHARACTER_CATALOG,
  characterById,
  characterByName,
  selectionCommand,
} from "../.test-dist/character/catalog.js";


test("character catalog maps model A and C slots to HearthGhost names", () => {
  const younghee = characterById("younghee");
  const cheolsu = characterById("cheolsu");

  assert.equal(CHARACTER_CATALOG.length, 2);
  assert.equal(younghee?.name, "영희");
  assert.equal(younghee?.sample, "AvatarSample_Y");
  assert.equal(younghee?.assetUrl, "/models/AvatarSample_Y.vrm");
  assert.equal(cheolsu?.name, "철수");
  assert.equal(cheolsu?.sample, "AvatarSample_C");
  assert.equal(cheolsu?.assetUrl, "/models/AvatarSample_C.vrm");
});

test("character assets are local paths and selection commands are deterministic", () => {
  for (const character of CHARACTER_CATALOG) {
    assert.match(character.assetUrl, /^\/models\/[A-Za-z0-9_.-]+\.vrm$/);
    assert.equal(character.assetUrl.includes("://"), false);
    assert.equal(selectionCommand(character), `캐릭터: ${character.name}`);
    assert.equal(characterByName(character.name)?.id, character.id);
  }
});

test("voice profiles remain visibly distinct even when Android exposes one local voice", () => {
  const younghee = characterById("younghee");
  const cheolsu = characterById("cheolsu");

  assert.notEqual(younghee?.voice.pitch, cheolsu?.voice.pitch);
  assert.notEqual(younghee?.voice.rate, cheolsu?.voice.rate);
});
