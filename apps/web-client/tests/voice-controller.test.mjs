import assert from "node:assert/strict";
import test from "node:test";

import { AttentionController } from "../.test-dist/attention/controller.js";
import { TextConversationController } from "../.test-dist/conversation/controller.js";
import { ClientNode } from "../.test-dist/node/client-node.js";
import { VoiceConversationController } from "../.test-dist/voice/controller.js";

const characterProfile = { name: "HearthGhost" };

class Clock {
  constructor() {
    this.now = 1_000;
  }
  nowMillis() {
    return this.now;
  }
}

class NodePlatform {
  async connect() {
    return {
      authenticated: true,
      nodeId: "android-development-01",
      technicalSessionId: "node-session-voice",
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
      conversationSessionId: "conversation-voice",
      characterProfile,
      events: [],
    };
  }
  async submit(conversationSessionId, text) {
    return {
      conversationSessionId,
      responseText: `voice: ${text}`,
      characterProfile,
      events: [],
    };
  }
  async end() {
    return [];
  }
}

async function fixture() {
  const node = new ClientNode(new NodePlatform());
  await node.connect({ kind: "platform-managed", reference: "voice-test" });
  const conversation = new TextConversationController(
    node,
    new ConversationTransport(),
    () => {},
  );
  const clock = new Clock();
  const attention = new AttentionController(20_000, clock);
  return {
    clock,
    attention,
    voice: new VoiceConversationController(attention, conversation),
  };
}

test("voice transcript requires explicit active attention", async () => {
  const { voice } = await fixture();

  await assert.rejects(
    () => voice.acceptTranscript({ text: "hello", source: "on_device_stt" }),
    /without active attention/,
  );
});

test("on-device transcript enters the existing conversation path", async () => {
  const { attention, voice } = await fixture();
  attention.wakeByTouch();

  const result = await voice.acceptTranscript({
    text: "안녕 고스트",
    source: "on_device_stt",
    confidence: 0.91,
  });

  assert.equal(result.responseText, "voice: 안녕 고스트");
  assert.equal(result.conversationSessionId, "conversation-voice");
  assert.deepEqual(result.characterProfile, characterProfile);
  assert.equal(attention.snapshot().state, "engaged");
});

test("voice gate rejects non-local source and malformed confidence", async () => {
  const { attention, voice } = await fixture();
  attention.wakeByTouch();

  await assert.rejects(
    () => voice.acceptTranscript({ text: "hello", source: "cloud_stt" }),
    /Only on-device/,
  );
  await assert.rejects(
    () => voice.acceptTranscript({
      text: "hello",
      source: "on_device_stt",
      confidence: 1.5,
    }),
    /confidence is invalid/,
  );
});

test("expired attention rejects a late voice result", async () => {
  const { attention, clock, voice } = await fixture();
  attention.wakeByTouch();
  clock.now += 20_001;

  await assert.rejects(
    () => voice.acceptTranscript({ text: "too late", source: "on_device_stt" }),
    /without active attention/,
  );
});
