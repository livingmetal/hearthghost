import {
  parseCharacterSemanticEvent,
  type CharacterSemanticEvent,
} from "../character/semantic.js";

export interface PendingActionProposal {
  readonly name: string;
  readonly arguments: Readonly<Record<string, string>>;
  readonly authorizationStatus: "pending_policy";
  readonly executionStatus: "not_executed";
}

export interface ConversationWireResult {
  readonly requestId: string;
  readonly accepted: boolean;
  readonly reasonCode: string;
  readonly nodeSessionId: string | null;
  readonly conversationSessionId: string | null;
  readonly responseText: string | null;
  readonly events: readonly CharacterSemanticEvent[];
  readonly proposedActions: readonly PendingActionProposal[];
}

const ALLOWED_FIELDS = new Set([
  "contract_version",
  "message_type",
  "request_id",
  "outcome",
  "reason_code",
  "node_session_id",
  "conversation_session_id",
  "response_text",
  "events",
  "proposed_actions",
]);

export function parseConversationWireResult(value: unknown): ConversationWireResult {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("Conversation result must be an object");
  }
  const document = value as Record<string, unknown>;
  if (Object.keys(document).some((field) => !ALLOWED_FIELDS.has(field))) {
    throw new Error("Conversation result contains an unknown or secret-bearing field");
  }
  if (
    document.contract_version !== "1.0" ||
    document.message_type !== "conversation.result" ||
    typeof document.request_id !== "string" ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(document.request_id) ||
    (document.outcome !== "accepted" && document.outcome !== "denied") ||
    typeof document.reason_code !== "string" ||
    document.reason_code.length < 1 ||
    document.reason_code.length > 128
  ) {
    throw new Error("Conversation result identity is invalid");
  }

  const nodeSessionId = optionalBoundedString(document.node_session_id, 128);
  const conversationSessionId = optionalBoundedString(
    document.conversation_session_id,
    128,
  );
  const responseText = optionalBoundedString(document.response_text, 8_000);
  const rawEvents = document.events ?? [];
  if (!Array.isArray(rawEvents) || rawEvents.length > 8) {
    throw new Error("Conversation semantic event list is invalid");
  }
  const events = Object.freeze(rawEvents.map(parseCharacterSemanticEvent));
  const rawProposals = document.proposed_actions ?? [];
  if (!Array.isArray(rawProposals) || rawProposals.length > 8) {
    throw new Error("Conversation proposal list is invalid");
  }
  const proposedActions = Object.freeze(rawProposals.map(parsePendingProposal));

  return Object.freeze({
    requestId: document.request_id,
    accepted: document.outcome === "accepted",
    reasonCode: document.reason_code,
    nodeSessionId,
    conversationSessionId,
    responseText,
    events,
    proposedActions,
  });
}

function optionalBoundedString(value: unknown, maxLength: number): string | null {
  if (value === undefined) {
    return null;
  }
  if (typeof value !== "string" || value.length < 1 || value.length > maxLength) {
    throw new Error("Conversation result contains an invalid bounded string");
  }
  return value;
}

function parsePendingProposal(value: unknown): PendingActionProposal {
  if (
    typeof value !== "object" ||
    value === null ||
    Array.isArray(value) ||
    Object.keys(value).length !== 4 ||
    !("name" in value) ||
    !("arguments" in value) ||
    !("authorization_status" in value) ||
    !("execution_status" in value) ||
    typeof value.name !== "string" ||
    !/^[a-z][a-z0-9_-]{0,63}(\.[a-z][a-z0-9_-]{0,63})+$/.test(value.name) ||
    typeof value.arguments !== "object" ||
    value.arguments === null ||
    Array.isArray(value.arguments) ||
    value.authorization_status !== "pending_policy" ||
    value.execution_status !== "not_executed"
  ) {
    throw new Error("Conversation proposal is authoritative or malformed");
  }
  const argumentsCopy: Record<string, string> = {};
  for (const [key, argument] of Object.entries(value.arguments)) {
    if (typeof argument !== "string" || key.length > 128 || argument.length > 256) {
      throw new Error("Conversation proposal arguments are invalid");
    }
    argumentsCopy[key] = argument;
  }
  return Object.freeze({
    name: value.name,
    arguments: Object.freeze(argumentsCopy),
    authorizationStatus: "pending_policy",
    executionStatus: "not_executed",
  });
}
