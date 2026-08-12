import assert from "node:assert/strict";
import test from "node:test";

import {
  WINDOWS_CREDENTIAL_REFERENCE,
  WindowsNodePlatform,
} from "../.test-dist/node/windows-platform.js";

const youngheeProfile = {
  name: "영희",
  humor: "moderate",
  verbosity: "normal",
  formality: "casual",
  initiative: "low",
};

function fakeBridge(handler) {
  return { request: handler };
}

test("Windows platform accepts only the approved CurrentUser store credential reference", async () => {
  const platform = new WindowsNodePlatform(fakeBridge(async () => ({
    authenticated: true,
    nodeId: "windows-development-01",
    technicalSessionId: "node-session-1",
    trust: "trusted",
    grantedCapabilities: ["conversation.text"],
  })));

  await assert.rejects(
    platform.connect({ kind: "platform-managed", reference: "file:pfx" }),
    /credential reference is not approved/,
  );

  const connected = await platform.connect({
    kind: "platform-managed",
    reference: WINDOWS_CREDENTIAL_REFERENCE,
  });
  assert.equal(connected.authenticated, true);
  assert.equal(connected.trust, "trusted");
  assert.deepEqual(connected.grantedCapabilities, ["conversation.text"]);
});

test("Windows platform parses strict display-only conversation results", async () => {
  const calls = [];
  const platform = new WindowsNodePlatform(fakeBridge(async (method, params) => {
    calls.push([method, params]);
    if (method === "conversation.open") {
      return {
        nodeSessionId: "node-session-1",
        conversationSessionId: "conversation-1",
        characterProfile: youngheeProfile,
        events: [{ type: "character.state", payload: { state: "engaged" } }],
      };
    }
    if (method === "conversation.text") {
      return {
        conversationSessionId: "conversation-1",
        responseText: "응, 듣고 있어.",
        characterProfile: youngheeProfile,
        events: [],
      };
    }
    if (method === "conversation.close") {
      return {
        characterProfile: youngheeProfile,
        events: [],
      };
    }
    throw new Error(`unexpected method ${method}`);
  }));

  const opened = await platform.open("node-session-1");
  assert.equal(opened.characterProfile.name, "영희");
  const reply = await platform.submit("conversation-1", "안녕");
  assert.equal(reply.responseText, "응, 듣고 있어.");
  await platform.end("conversation-1");
  assert.deepEqual(calls.map(([method]) => method), [
    "conversation.open",
    "conversation.text",
    "conversation.close",
  ]);
});

test("Windows platform rejects authority-looking character profile fields", async () => {
  const platform = new WindowsNodePlatform(fakeBridge(async () => ({
    nodeSessionId: "node-session-1",
    conversationSessionId: "conversation-1",
    characterProfile: { ...youngheeProfile, capability: "camera.stream" },
    events: [],
  })));

  await assert.rejects(platform.open("node-session-1"));
});
