export type NodeTrustState = "unknown" | "untrusted" | "trusted" | "revoked";

export interface CredentialReference {
  readonly kind: "platform-managed";
  readonly reference: string;
}

export interface SecureNodeSession {
  readonly authenticated: boolean;
  readonly nodeId: string;
  readonly technicalSessionId: string;
  readonly trust: NodeTrustState;
  readonly grantedCapabilities: readonly string[];
}

export interface NodePlatformPort {
  connect(credential: CredentialReference): Promise<SecureNodeSession>;
  disconnect(): Promise<void>;
}

export class SecureNodeTransportUnavailableError extends Error {
  constructor(message = "Secure Node transport is unavailable on this platform") {
    super(message);
    this.name = "SecureNodeTransportUnavailableError";
  }
}
