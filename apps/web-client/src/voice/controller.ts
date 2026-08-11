import type { AttentionController } from "../attention/controller.js";
import type {
  ConversationSnapshot,
  TextConversationController,
} from "../conversation/controller.js";
import type { VoiceTranscriptResult } from "./android-voice.js";

export class VoiceConversationController {
  constructor(
    private readonly attention: AttentionController,
    private readonly conversation: TextConversationController,
  ) {}

  async acceptTranscript(result: VoiceTranscriptResult): Promise<ConversationSnapshot> {
    if (result.source !== "on_device_stt") {
      throw new Error("Only on-device speech transcripts are accepted");
    }
    if (
      typeof result.text !== "string"
      || result.text.trim() === ""
      || result.text.length > 4_000
      || result.text.includes("\u0000")
    ) {
      throw new Error("Voice transcript is invalid");
    }
    if (
      result.confidence !== undefined
      && (
        typeof result.confidence !== "number"
        || !Number.isFinite(result.confidence)
        || result.confidence < 0
        || result.confidence > 1
      )
    ) {
      throw new Error("Voice transcript confidence is invalid");
    }
    if (!this.attention.canAcceptConversationInput()) {
      throw new Error("Voice transcript arrived without active attention");
    }
    if (this.conversation.snapshot().conversationSessionId === null) {
      await this.conversation.open();
    }
    const snapshot = await this.conversation.submit(result.text);
    this.attention.recordAddressedActivity();
    return snapshot;
  }
}
