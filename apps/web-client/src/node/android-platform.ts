import { registerPlugin } from "@capacitor/core";

import type {
  OpenConversationResult,
  TextConversationResult,
  TextConversationTransportPort,
} from "../conversation/controller.js";
import { parseCharacterSemanticEvent } from "../character/semantic.js";
import type {
  CredentialReference,
  NodePlatformPort,
  NodeTrustState,
  SecureNodeSession,
} from "./platform.js";

export const ANDROID_NODE_ID = "android-development-01";
export const ANDROID_CREDENTIAL_REFERENCE = "hearthghost.android.development.01";

interface NativeConnectResult {
  readonly authenticated: boolean;
  readonly nodeId: string;
  readonly technicalSessionId: string;
  readonly trust: NodeTrustState;
  readonly grantedCapabilities: readonly string[];
}

interface NativeConversationResult {
  readonly conversationSessionId: string;
  readonly nodeSessionId?: string;
  readonly responseText?: string;
  readonly events: readonly unknown[];
}

interface NativeIdentityStatus {
  readonly keyPresent: boolean;
  readonly certificateInstalled: boolean;
  readonly nonExportable: boolean;
  readonly credentialReference: string;
}

interface NodeTransportNativePlugin {
  identityStatus(): Promise<NativeIdentityStatus>;
  createEnrollmentRequest(): Promise<{
    readonly nodeId: string;
    readonly credentialReference: string;
    readonly csrPem: string;
    readonly csrSha256: string;
  }>;
  installCertificateChain(options: {
    readonly nodeCertificatePem: string;
    readonly authorityCertificatePem: string;
  }): Promise<NativeIdentityStatus>;
  connect(): Promise<NativeConnectResult>;
  disconnect(): Promise<void>;
  openConversation(options: {
    readonly nodeSessionId: string;
  }): Promise<NativeConversationResult>;
  sendText(options: {
    readonly conversationSessionId: string;
    readonly text: string;
  }): Promise<NativeConversationResult>;
  closeConversation(options: {
    readonly conversationSessionId: string;
  }): Promise<NativeConversationResult>;
}

const NativeNodeTransport = registerPlugin<NodeTransportNativePlugin>(
  "NodeTransport",
);

export class AndroidNodePlatform
  implements NodePlatformPort, TextConversationTransportPort
{
  async connect(credential: CredentialReference): Promise<SecureNodeSession> {
    if (credential.reference !== ANDROID_CREDENTIAL_REFERENCE) {
      throw new Error("Android Node credential reference is not approved");
    }
    return NativeNodeTransport.connect();
  }

  async disconnect(): Promise<void> {
    await NativeNodeTransport.disconnect();
  }

  async open(nodeSessionId: string): Promise<OpenConversationResult> {
    const result = await NativeNodeTransport.openConversation({ nodeSessionId });
    if (result.nodeSessionId === undefined) {
      throw new Error("Native conversation open omitted the Node session");
    }
    return {
      nodeSessionId: result.nodeSessionId,
      conversationSessionId: result.conversationSessionId,
      events: result.events.map(parseCharacterSemanticEvent),
    };
  }

  async submit(
    conversationSessionId: string,
    text: string,
  ): Promise<TextConversationResult> {
    const result = await NativeNodeTransport.sendText({
      conversationSessionId,
      text,
    });
    if (result.responseText === undefined) {
      throw new Error("Native conversation response omitted text");
    }
    return {
      conversationSessionId: result.conversationSessionId,
      responseText: result.responseText,
      events: result.events.map(parseCharacterSemanticEvent),
    };
  }

  async end(conversationSessionId: string): Promise<readonly unknown[]> {
    const result = await NativeNodeTransport.closeConversation({
      conversationSessionId,
    });
    return result.events.map(parseCharacterSemanticEvent);
  }

  identityStatus(): Promise<NativeIdentityStatus> {
    return NativeNodeTransport.identityStatus();
  }

  createEnrollmentRequest(): ReturnType<
    NodeTransportNativePlugin["createEnrollmentRequest"]
  > {
    return NativeNodeTransport.createEnrollmentRequest();
  }

  installCertificateChain(
    nodeCertificatePem: string,
    authorityCertificatePem: string,
  ): Promise<NativeIdentityStatus> {
    return NativeNodeTransport.installCertificateChain({
      nodeCertificatePem,
      authorityCertificatePem,
    });
  }
}
