import assert from "node:assert/strict";
import test from "node:test";

import { TextConversationController } from "../.test-dist/conversation/controller.js";
import { ClientNode } from "../.test-dist/node/client-node.js";

const credential = { kind: "platform-managed", reference: "test-alias" };

class NodePlatform {
  constructor() {
    this.sessionId = "node-session-1";
  }
  async connect() {
    return {
      authenticated: true,
      nodeId: "client-living-room",
      technicalSessionId: this.sessionId,
      trust: "trusted",
      grantedCapabilities: ["conversation.text"],
    };
  }
  async disconnect() {}
}

class ConversationTransport {
  async open(nodeSessionId) {
    return {
      nodeSessionId,
      conversationSessionId: "conversation-1",
      events: [{ type: "character.state", payload: { state: "listening" } }],
    };
  }
  async submit(conversationSessionId, text) {
    return {
      conversationSessionId,
      responseText: `fake: ${text}`,
      events: [
        { type: "character.state", payload: { state: "thinking" } },
        { type: "character.state", payload: { state: "speaking" } },
        { type: "character.state", payload: { state: "engaged" } },
      ],
    };
  }
  async end() {
    return [{ type: "character.state", payload: { state: "sleeping" } }];
  }
}

test("text session remains distinct and emits semantic events", async () => {
  const node = new ClientNode(new NodePlatform());
  await node.connect(credential);
  const events = [];
  const controller = new TextConversationController(
    node,
    new ConversationTransport(),
    (event) => events.push(event),
  );

  const opened = await controller.open();
  const response = await controller.submit("hello");

  assert.equal(opened.nodeSessionId, "node-session-1");
  assert.equal(opened.conversationSessionId, "conversation-1");
  assert.notEqual(opened.nodeSessionId, opened.conversationSessionId);
  assert.equal(response.responseText, "fake: hello");
  assert.deepEqual(events.map((event) => event.payload.state), [
    "listening",
    "thinking",
    "speaking",
    "engaged",
  ]);
});

test("conversation cannot start without trust and grant", async () => {
  const node = new ClientNode({
    async connect() {
      return {
        authenticated: true,
        nodeId: "client-living-room",
        technicalSessionId: "node-session-1",
        trust: "untrusted",
        grantedCapabilities: ["conversation.text"],
      };
    },
    async disconnect() {},
  });
  await node.connect(credential);
  const controller = new TextConversationController(
    node,
    new ConversationTransport(),
    () => {},
  );

  await assert.rejects(() => controller.open(), /trusted Node session/);
});

test("Node reconnect invalidates the old conversation binding", async () => {
  const platform = new NodePlatform();
  const node = new ClientNode(platform);
  await node.connect(credential);
  const controller = new TextConversationController(
    node,
    new ConversationTransport(),
    () => {},
  );
  await controller.open();
  await node.suspend();
  platform.sessionId = "node-session-2";
  await node.resume();

  await assert.rejects(
    () => controller.submit("must re-open"),
    /not bound to this trusted Node session/,
  );
});

test("conversation end does not disconnect the Node session", async () => {
  const node = new ClientNode(new NodePlatform());
  await node.connect(credential);
  const controller = new TextConversationController(
    node,
    new ConversationTransport(),
    () => {},
  );
  await controller.open();

  const ended = await controller.end();

  assert.equal(ended.conversationSessionId, null);
  assert.equal(node.snapshot().connection, "connected");
  assert.equal(node.snapshot().technicalSessionId, "node-session-1");
});
