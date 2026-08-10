import assert from "node:assert/strict";
import test from "node:test";

import { BrowserDevelopmentNodePlatform } from "../.test-dist/node/browser-platform.js";
import { ClientNode } from "../.test-dist/node/client-node.js";

const credential = Object.freeze({
  kind: "platform-managed",
  reference: "android-keystore-alias",
});

class ScriptedPlatform {
  constructor(sessions) {
    this.sessions = [...sessions];
    this.disconnectCount = 0;
  }

  async connect() {
    const next = this.sessions.shift();
    if (next === undefined) {
      throw new Error("No scripted secure session");
    }
    return next;
  }

  async disconnect() {
    this.disconnectCount += 1;
  }
}

function session(overrides = {}) {
  return {
    authenticated: true,
    nodeId: "client-living-room",
    technicalSessionId: "node-session-1",
    trust: "trusted",
    grantedCapabilities: ["conversation.text"],
    ...overrides,
  };
}

test("authenticated but untrusted client cannot use a granted-looking capability", async () => {
  const node = new ClientNode(new ScriptedPlatform([
    session({ trust: "untrusted" }),
  ]));

  const snapshot = await node.connect(credential);

  assert.equal(snapshot.connection, "connected");
  assert.equal(snapshot.trust, "untrusted");
  assert.equal(node.canUseCapability("conversation.text"), false);
});

test("trusted client still requires an explicit capability grant", async () => {
  const node = new ClientNode(new ScriptedPlatform([
    session({ grantedCapabilities: [] }),
  ]));

  await node.connect(credential);

  assert.equal(node.canUseCapability("conversation.text"), false);
});

test("only an authenticated trusted session with a grant is capability-aware", async () => {
  const node = new ClientNode(new ScriptedPlatform([session()]));

  await node.connect(credential);

  assert.equal(node.canUseCapability("conversation.text"), true);
  assert.equal(node.canUseCapability("speaker"), false);
});

test("transport authentication failure is closed and reports no session", async () => {
  const node = new ClientNode(new ScriptedPlatform([
    session({ authenticated: false }),
  ]));

  const snapshot = await node.connect(credential);

  assert.equal(snapshot.connection, "failed");
  assert.equal(snapshot.nodeId, null);
  assert.equal(snapshot.technicalSessionId, null);
  assert.match(snapshot.error, /authenticated mTLS/);
});

test("suspend closes the technical session and resume creates another", async () => {
  const platform = new ScriptedPlatform([
    session(),
    session({ technicalSessionId: "node-session-2" }),
  ]);
  const node = new ClientNode(platform);

  const first = await node.connect(credential);
  const suspended = await node.suspend();
  const resumed = await node.resume();

  assert.equal(first.technicalSessionId, "node-session-1");
  assert.equal(suspended.connection, "disconnected");
  assert.equal(resumed.technicalSessionId, "node-session-2");
  assert.equal(platform.disconnectCount, 1);
});

test("revoked Node cannot use capabilities after reconnect", async () => {
  const node = new ClientNode(new ScriptedPlatform([
    session(),
    session({ trust: "revoked", technicalSessionId: "node-session-2" }),
  ]));

  await node.connect(credential);
  await node.suspend();
  const revoked = await node.resume();

  assert.equal(revoked.trust, "revoked");
  assert.equal(node.canUseCapability("conversation.text"), false);
});

test("browser development adapter never downgrades secure transport", async () => {
  const node = new ClientNode(new BrowserDevelopmentNodePlatform());

  const snapshot = await node.connect(credential);

  assert.equal(snapshot.connection, "failed");
  assert.match(snapshot.error, /no native mTLS credential adapter/);
});
