import assert from "node:assert/strict";
import test from "node:test";

import {
  CHARACTER_PREFERENCE_STORAGE_KEY,
  DEFAULT_CHARACTER_ID,
  loadPreferredCharacterId,
  savePreferredCharacterId,
} from "../.test-dist/character/preferences.js";

class MemoryStorage {
  values = new Map();

  getItem(key) {
    return this.values.get(key) ?? null;
  }

  setItem(key, value) {
    this.values.set(key, value);
  }
}

test("character preference defaults to a bundled VRM character", () => {
  const storage = new MemoryStorage();

  assert.equal(DEFAULT_CHARACTER_ID, "younghee");
  assert.equal(loadPreferredCharacterId(storage), "younghee");

  storage.setItem(CHARACTER_PREFERENCE_STORAGE_KEY, "unknown");
  assert.equal(loadPreferredCharacterId(storage), "younghee");
});

test("saved character selection survives a new preference read", () => {
  const storage = new MemoryStorage();

  assert.equal(savePreferredCharacterId(storage, "cheolsu"), true);
  assert.equal(loadPreferredCharacterId(storage), "cheolsu");
});

test("unavailable browser storage fails closed to the bundled default", () => {
  const brokenStorage = {
    getItem() {
      throw new Error("storage unavailable");
    },
    setItem() {
      throw new Error("storage unavailable");
    },
  };

  assert.equal(loadPreferredCharacterId(brokenStorage), "younghee");
  assert.equal(savePreferredCharacterId(brokenStorage, "cheolsu"), false);
  assert.equal(loadPreferredCharacterId(null), "younghee");
});
