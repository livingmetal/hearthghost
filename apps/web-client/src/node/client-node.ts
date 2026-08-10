import type {
  CredentialReference,
  NodePlatformPort,
  NodeTrustState,
  SecureNodeSession,
} from "./platform.js";

export type ConnectionState =
  | "disconnected"
  | "connecting"
  | "connected"
  | "failed";

export interface ClientNodeSnapshot {
  readonly connection: ConnectionState;
  readonly nodeId: string | null;
  readonly technicalSessionId: string | null;
  readonly trust: NodeTrustState;
  readonly grantedCapabilities: readonly string[];
  readonly error: string | null;
}

const INITIAL_SNAPSHOT: ClientNodeSnapshot = Object.freeze({
  connection: "disconnected",
  nodeId: null,
  technicalSessionId: null,
  trust: "unknown",
  grantedCapabilities: Object.freeze([]),
  error: null,
});

export class ClientNode {
  private current: ClientNodeSnapshot = INITIAL_SNAPSHOT;
  private credential: CredentialReference | null = null;

  constructor(private readonly platform: NodePlatformPort) {}

  snapshot(): ClientNodeSnapshot {
    return this.current;
  }

  async connect(credential: CredentialReference): Promise<ClientNodeSnapshot> {
    if (credential.kind !== "platform-managed" || credential.reference.trim() === "") {
      throw new Error("A non-empty platform-managed credential reference is required");
    }

    this.credential = credential;
    this.current = { ...INITIAL_SNAPSHOT, connection: "connecting" };

    try {
      const session = await this.platform.connect(credential);
      this.current = this.acceptSession(session);
    } catch (error) {
      this.current = {
        ...INITIAL_SNAPSHOT,
        connection: "failed",
        error: error instanceof Error ? error.message : "Secure Node connection failed",
      };
    }
    return this.current;
  }

  async disconnect(): Promise<ClientNodeSnapshot> {
    await this.platform.disconnect();
    this.current = INITIAL_SNAPSHOT;
    return this.current;
  }

  async suspend(): Promise<ClientNodeSnapshot> {
    return this.disconnect();
  }

  async resume(): Promise<ClientNodeSnapshot> {
    if (this.credential === null) {
      return this.current;
    }
    return this.connect(this.credential);
  }

  canUseCapability(capability: string): boolean {
    return (
      this.current.connection === "connected" &&
      this.current.trust === "trusted" &&
      this.current.grantedCapabilities.includes(capability)
    );
  }

  private acceptSession(session: SecureNodeSession): ClientNodeSnapshot {
    if (!session.authenticated) {
      throw new Error("Node transport did not establish authenticated mTLS");
    }
    if (session.nodeId.trim() === "" || session.technicalSessionId.trim() === "") {
      throw new Error("Authenticated Node session metadata is incomplete");
    }

    const capabilities = Object.freeze([...new Set(session.grantedCapabilities)]);
    return Object.freeze({
      connection: "connected",
      nodeId: session.nodeId,
      technicalSessionId: session.technicalSessionId,
      trust: session.trust,
      grantedCapabilities: capabilities,
      error: null,
    });
  }
}
