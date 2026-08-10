import assert from "node:assert/strict";
import test from "node:test";

import { parseConversationWireResult } from "../.test-dist/conversation/protocol.js";

function result(overrides = {}) {
  return {
    contract_version: "1.0",
    message_type: "conversation.result",
    request_id: "123e4567-e89b-12d3-a456-426614174000",
    outcome: "accepted",
    reason_code: "allowed",
    node_session_id: "node-session-1",
    conversation_session_id: "conversation-1",
    response_text: "Fake response",
    events: [{ type: "character.state", payload: { state: "engaged" } }],
    proposed_actions: [],
    ...overrides,
  };
}

test("wire result exposes text and semantic events without secrets", () => {
  const parsed = parseConversationWireResult(result());

  assert.equal(parsed.accepted, true);
  assert.equal(parsed.responseText, "Fake response");
  assert.deepEqual(parsed.events[0], {
    type: "character.state",
    payload: { state: "engaged" },
  });
  assert.deepEqual(Object.keys(parsed).sort(), [
    "accepted",
    "conversationSessionId",
    "events",
    "nodeSessionId",
    "proposedActions",
    "reasonCode",
    "requestId",
    "responseText",
  ]);
});

test("client rejects provider secrets and renderer commands", () => {
  assert.throws(
    () => parseConversationWireResult(result({ provider_api_key: "forbidden" })),
    /secret-bearing field/,
  );
  assert.throws(
    () => parseConversationWireResult(result({
      events: [{
        type: "character.state",
        payload: { state: "speaking", blendshape: "Fcl_MTH_A" },
      }],
    })),
    /malformed semantic character event/,
  );
});

test("client accepts only pending and explicitly unexecuted proposals", () => {
  const pending = parseConversationWireResult(result({
    proposed_actions: [{
      name: "home.light.off",
      arguments: { area: "living_room" },
      authorization_status: "pending_policy",
      execution_status: "not_executed",
    }],
  }));
  assert.equal(pending.proposedActions[0].executionStatus, "not_executed");

  for (const proposal of [
    {
      name: "home.light.off",
      arguments: {},
      authorization_status: "authorized",
      execution_status: "not_executed",
    },
    {
      name: "home.light.off",
      arguments: {},
      authorization_status: "pending_policy",
      execution_status: "executed",
    },
  ]) {
    assert.throws(
      () => parseConversationWireResult(result({ proposed_actions: [proposal] })),
      /authoritative or malformed/,
    );
  }
});
