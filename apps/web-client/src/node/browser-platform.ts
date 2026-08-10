import {
  SecureNodeTransportUnavailableError,
  type CredentialReference,
  type NodePlatformPort,
  type SecureNodeSession,
} from "./platform.js";

/**
 * The browser UI is useful for presentation development, but it is not the
 * trusted Android Node boundary. It fails rather than downgrading mTLS.
 */
export class BrowserDevelopmentNodePlatform implements NodePlatformPort {
  async connect(_credential: CredentialReference): Promise<SecureNodeSession> {
    throw new SecureNodeTransportUnavailableError(
      "This browser build has no native mTLS credential adapter. Use the explicitly configured fake adapter for tests or a reviewed native adapter.",
    );
  }

  async disconnect(): Promise<void> {
    // No connection can be opened by this adapter.
  }
}
