import assert from "node:assert/strict";
import test from "node:test";

import { AttentionController } from "../.test-dist/attention/controller.js";

class FakeClock {
  constructor() {
    this.now = 1_000;
  }
  nowMillis() {
    return this.now;
  }
  advance(milliseconds) {
    this.now += milliseconds;
  }
}

test("attention is sleeping until explicit touch wake", () => {
  const clock = new FakeClock();
  const attention = new AttentionController(20_000, clock);

  assert.equal(attention.snapshot().state, "sleeping");
  assert.equal(attention.canAcceptConversationInput(), false);

  const awake = attention.wakeByTouch();
  assert.equal(awake.state, "engaged");
  assert.equal(awake.remainingMillis, 20_000);
  assert.equal(attention.canAcceptConversationInput(), true);
});

test("addressed activity extends the bounded attention window", () => {
  const clock = new FakeClock();
  const attention = new AttentionController(20_000, clock);
  attention.wakeByTouch();
  clock.advance(15_000);

  attention.recordAddressedActivity();
  clock.advance(10_000);

  assert.equal(attention.canAcceptConversationInput(), true);
  assert.equal(attention.snapshot().remainingMillis, 10_000);
});

test("idle attention fails closed back to sleeping", () => {
  const clock = new FakeClock();
  const attention = new AttentionController(20_000, clock);
  attention.wakeByTouch();
  clock.advance(20_000);

  assert.equal(attention.expireIfIdle(), true);
  assert.equal(attention.snapshot().state, "sleeping");
  assert.equal(attention.canAcceptConversationInput(), false);
});

test("unaddressed activity cannot silently wake the client", () => {
  const attention = new AttentionController(20_000, new FakeClock());

  assert.throws(
    () => attention.recordAddressedActivity(),
    /requires active attention/,
  );
  assert.equal(attention.snapshot().state, "sleeping");
});
