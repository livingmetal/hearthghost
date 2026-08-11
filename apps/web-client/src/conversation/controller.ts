import type { CharacterDisplayProfile } from "../character/profile.js";
import type { ClientNode } from "../node/client-node.js";

export interface OpenConversationResult {
  readonly conversationSessionId: string;
  readonly nodeSessionId: string;
  readonly characterProfile: CharacterDisplayProfile;
  readonly events: readonly unknown[];
}

export interface TextConversationResult {
  readonly conversationSessionId: string;
  readonly responseText: string;
  readonly characterProfile: CharacterDisplayProfile;
  readonly events: readonly unknown[];
}

export interface TextConversationTransportPort {
  open(nodeSessionId: string): Promise<OpenConversationResult>;
  submit(conversationSessionId: string, text: string): Promise<TextConversationResult>;
  end(conversationSessionId: string): Promise<readonly unknown[]>;
}

export interface ConversationSnapshot {
  readonly conversationSessionId: string | null;
  readonly nodeSessionId: string | null;
  readonly responseText: string | null;
  readonly characterProfile: CharacterDisplayProfile | null;
}

export class TextConversationController {
  private conversationSessionId: string | null = null;
  private nodeSessionId: string | null = null;
  private responseText: string | null = null;
  private characterProfile: CharacterDisplayProfile | null = null;

  constructor(
    private readonly node: ClientNode,
    private readonly transport: TextConversationTransportPort,
    private readonly publishSemanticEvent: (event: unknown) => void,
  ) {}

  snapshot(): ConversationSnapshot {
    return Object.freeze({
      conversationSessionId: this.conversationSessionId,
      nodeSessionId: this.nodeSessionId,
      responseText: this.responseText,
      characterProfile: this.characterProfile,
    });
  }

  async open(): Promise<ConversationSnapshot> {
    const node = this.node.snapshot();
    if (!this.node.canUseCapability("conversation.text") || node.technicalSessionId === null) {
      throw new Error("A trusted Node session with conversation.text grant is required");
    }
    const opened = await this.transport.open(node.technicalSessionId);
    if (
      opened.nodeSessionId !== node.technicalSessionId ||
      opened.conversationSessionId.trim() === "" ||
      opened.conversationSessionId === node.technicalSessionId
    ) {
      throw new Error("Conversation transport returned invalid session identity");
    }
    this.nodeSessionId = node.technicalSessionId;
    this.conversationSessionId = opened.conversationSessionId;
    this.responseText = null;
    this.characterProfile = opened.characterProfile;
    this.publish(opened.events);
    return this.snapshot();
  }

  async submit(text: string): Promise<ConversationSnapshot> {
    const normalized = text.trim();
    if (normalized === "" || normalized.length > 4_000 || normalized.includes("\u0000")) {
      throw new Error("Text input must contain 1 to 4000 safe characters");
    }
    const nodeSessionId = this.node.snapshot().technicalSessionId;
    if (
      this.conversationSessionId === null ||
      this.nodeSessionId === null ||
      nodeSessionId !== this.nodeSessionId ||
      !this.node.canUseCapability("conversation.text")
    ) {
      throw new Error("The active conversation is not bound to this trusted Node session");
    }
    const result = await this.transport.submit(this.conversationSessionId, normalized);
    if (
      result.conversationSessionId !== this.conversationSessionId ||
      result.responseText.trim() === ""
    ) {
      throw new Error("Conversation transport returned a malformed response");
    }
    this.responseText = result.responseText;
    this.characterProfile = result.characterProfile;
    this.publish(result.events);
    return this.snapshot();
  }

  async end(): Promise<ConversationSnapshot> {
    if (this.conversationSessionId !== null) {
      this.publish(await this.transport.end(this.conversationSessionId));
    }
    this.conversationSessionId = null;
    this.nodeSessionId = null;
    this.responseText = null;
    return this.snapshot();
  }

  private publish(events: readonly unknown[]): void {
    for (const event of events) {
      this.publishSemanticEvent(event);
    }
  }
}