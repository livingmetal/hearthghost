import type {
  OpenConversationResult,
  TextConversationResult,
  TextConversationTransportPort,
} from "../conversation/controller.js";
import { parseCharacterDisplayProfile } from "../character/profile.js";
import { parseCharacterSemanticEvent } from "../character/semantic.js";
import { WindowsWebViewBridge } from "../windows/webview-bridge.js";
import type {
  CredentialReference,
  NodePlatformPort,
  NodeTrustState,
  SecureNodeSession,
} from "./platform.js";

export const WINDOWS_CREDENTIAL_REFERENCE = "hearthghost.windows.current-user-store";

export class WindowsNodePlatform
  implements NodePlatformPort, TextConversationTransportPort
{
  constructor(private readonly bridge: WindowsWebViewBridge) {}

  async connect(credential: CredentialReference): Promise<SecureNodeSession> {
    if (credential.reference !== WINDOWS_CREDENTIAL_REFERENCE) {
      throw new Error("Windows Node credential reference is not approved");
    }
    const value = await this.bridge.request("node.connect");
    return parseSecureNodeSession(value);
  }

  async disconnect(): Promise<void> {
    await this.bridge.request("node.disconnect");
  }

  async open(nodeSessionId: string): Promise<OpenConversationResult> {
    const value = await this.bridge.request("conversation.open", { nodeSessionId });
    const result = requireRecord(value, "Windows conversation open result");
    return {
      nodeSessionId: requireString(result.nodeSessionId, "nodeSessionId", 128),
      conversationSessionId: requireString(result.conversationSessionId, "conversationSessionId", 128),
      characterProfile: parseCharacterDisplayProfile(result.characterProfile),
      events: requireArray(result.events, "events").map(parseCharacterSemanticEvent),
    };
  }

  async submit(
    conversationSessionId: string,
    text: string,
  ): Promise<TextConversationResult> {
    const value = await this.bridge.request("conversation.text", {
      conversationSessionId,
      text,
    });
    const result = requireRecord(value, "Windows conversation text result");
    return {
      conversationSessionId: requireString(result.conversationSessionId, "conversationSessionId", 128),
      responseText: requireString(result.responseText, "responseText", 8_000),
      characterProfile: parseCharacterDisplayProfile(result.characterProfile),
      events: requireArray(result.events, "events").map(parseCharacterSemanticEvent),
    };
  }

  async end(conversationSessionId: string): Promise<readonly unknown[]> {
    const value = await this.bridge.request("conversation.close", { conversationSessionId });
    const result = requireRecord(value, "Windows conversation close result");
    parseCharacterDisplayProfile(result.characterProfile);
    return requireArray(result.events, "events").map(parseCharacterSemanticEvent);
  }
}

function parseSecureNodeSession(value: unknown): SecureNodeSession {
  const result = requireRecord(value, "Windows Node session");
  const trust = result.trust;
  if (!isTrustState(trust)) {
    throw new Error("Windows Node session trust state is invalid");
  }
  const capabilities = requireArray(result.grantedCapabilities, "grantedCapabilities");
  if (capabilities.some((item) => typeof item !== "string" || item.length === 0 || item.length > 128)) {
    throw new Error("Windows Node capability list is invalid");
  }
  if (result.authenticated !== true) {
    throw new Error("Windows Node session is not authenticated");
  }
  return Object.freeze({
    authenticated: true,
    nodeId: requireString(result.nodeId, "nodeId", 128),
    technicalSessionId: requireString(result.technicalSessionId, "technicalSessionId", 128),
    trust,
    grantedCapabilities: Object.freeze(capabilities as string[]),
  });
}

function requireRecord(value: unknown, name: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${name} must be an object`);
  }
  return value as Record<string, unknown>;
}

function requireArray(value: unknown, name: string): unknown[] {
  if (!Array.isArray(value) || value.length > 16) {
    throw new Error(`${name} must be a bounded array`);
  }
  return value;
}

function requireString(value: unknown, name: string, maxLength: number): string {
  if (
    typeof value !== "string"
    || value.length === 0
    || value.length > maxLength
    || value !== value.trim()
    || value.includes("\u0000")
  ) {
    throw new Error(`${name} is invalid`);
  }
  return value;
}

function isTrustState(value: unknown): value is NodeTrustState {
  return value === "unknown"
    || value === "untrusted"
    || value === "trusted"
    || value === "revoked";
}
