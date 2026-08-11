import { Capacitor } from "@capacitor/core";

import "./styles.css";
import { BrowserDevelopmentNodePlatform } from "./node/browser-platform.js";
import {
  ANDROID_CREDENTIAL_REFERENCE,
  AndroidNodePlatform,
} from "./node/android-platform.js";
import { ClientNode } from "./node/client-node.js";
import type { NodePlatformPort } from "./node/platform.js";
import { loadCharacterRenderer } from "./character/renderer-loader.js";
import { CharacterViewport } from "./character/viewport.js";
import { TextConversationController } from "./conversation/controller.js";

const root = document.querySelector<HTMLDivElement>("#app");
if (root === null) {
  throw new Error("HearthGhost client root is missing");
}

const androidPlatform = Capacitor.getPlatform() === "android"
  ? new AndroidNodePlatform()
  : null;
const platform: NodePlatformPort = androidPlatform
  ?? new BrowserDevelopmentNodePlatform();
const node = new ClientNode(platform);

root.innerHTML = `
  <main class="app-shell">
    <header class="status-bar" aria-label="Privacy and security status">
      <span data-node-status>Node: disconnected</span>
      <span>Camera: denied</span>
      <span>Microphone: inactive</span>
      <span>Cloud media: denied</span>
    </header>
    <section class="character-viewport" aria-label="Character viewport">
    </section>
    <section class="interaction-panel">
      <label for="message">Text conversation</label>
      <form class="text-row" data-conversation>
        <input id="message" autocomplete="off" placeholder="Type to talk" />
        <button type="button" data-connect>Connect securely</button>
        <button type="submit" data-send disabled>Send</button>
      </form>
      <p class="notice" data-notice>Secure text transport is disconnected.</p>
      <output class="response" data-response aria-live="polite"></output>
      <details class="provisioning" data-provision hidden>
        <summary>Development Node enrollment</summary>
        <p data-identity-status>Android Keystore identity not checked.</p>
        <button type="button" data-create-csr>Create or inspect Keystore CSR</button>
        <label for="csr">CSR (public enrollment material)</label>
        <textarea id="csr" data-csr readonly></textarea>
        <label for="node-certificate">Signed Node certificate</label>
        <textarea id="node-certificate" data-node-certificate></textarea>
        <label for="authority-certificate">Development CA certificate</label>
        <textarea id="authority-certificate" data-authority-certificate></textarea>
        <button type="button" data-install-chain>Install verified chain</button>
      </details>
    </section>
  </main>
`;

const connectButton = root.querySelector<HTMLButtonElement>("[data-connect]");
const nodeStatus = root.querySelector<HTMLElement>("[data-node-status]");
const notice = root.querySelector<HTMLElement>("[data-notice]");
const response = root.querySelector<HTMLOutputElement>("[data-response]");
const form = root.querySelector<HTMLFormElement>("[data-conversation]");
const sendButton = root.querySelector<HTMLButtonElement>("[data-send]");
const viewportElement = root.querySelector<HTMLElement>(".character-viewport");
if (viewportElement === null) {
  throw new Error("CharacterViewport element is missing");
}
const rendererKind = document.documentElement.dataset.characterRenderer === "vrm"
  ? "vrm"
  : "dom";
const viewport = new CharacterViewport(
  viewportElement,
  await loadCharacterRenderer(rendererKind),
);
await viewport.mount();
const conversation = androidPlatform === null
  ? null
  : new TextConversationController(
      node,
      androidPlatform,
      (event) => viewport.present(event),
    );

function showSnapshot(): void {
  const snapshot = node.snapshot();
  if (nodeStatus !== null) {
    nodeStatus.textContent = `Node: ${snapshot.connection} / ${snapshot.trust}`;
  }
  if (sendButton !== null) {
    sendButton.disabled = !node.canUseCapability("conversation.text");
  }
}

connectButton?.addEventListener("click", async () => {
  await node.connect({
    kind: "platform-managed",
    reference: androidPlatform === null
      ? "not-provisioned"
      : ANDROID_CREDENTIAL_REFERENCE,
  });
  const snapshot = node.snapshot();
  showSnapshot();
  if (notice !== null && snapshot.error !== null) {
    notice.textContent = snapshot.error;
  } else if (notice !== null) {
    notice.textContent = node.canUseCapability("conversation.text")
      ? "Authenticated, trusted, and granted for text conversation."
      : "Authenticated, but explicit trust and conversation grant are required.";
  }
});

form?.addEventListener("submit", (event) => {
  event.preventDefault();
  void (async () => {
    const input = root.querySelector<HTMLInputElement>("#message");
    if (conversation === null || input === null) {
      if (notice !== null) {
        notice.textContent = "Native text transport is unavailable.";
      }
      return;
    }
    try {
      if (conversation.snapshot().conversationSessionId === null) {
        await conversation.open();
      }
      const snapshot = await conversation.submit(input.value);
      if (response !== null) {
        response.textContent = snapshot.responseText ?? "";
      }
      input.value = "";
    } catch (error) {
      if (notice !== null) {
        notice.textContent = error instanceof Error
          ? error.message
          : "Text conversation failed";
      }
    }
  })();
});

if (androidPlatform !== null) {
  const provisioning = root.querySelector<HTMLDetailsElement>("[data-provision]");
  const identityStatus = root.querySelector<HTMLElement>("[data-identity-status]");
  const csr = root.querySelector<HTMLTextAreaElement>("[data-csr]");
  const nodeCertificate = root.querySelector<HTMLTextAreaElement>(
    "[data-node-certificate]",
  );
  const authorityCertificate = root.querySelector<HTMLTextAreaElement>(
    "[data-authority-certificate]",
  );
  if (provisioning !== null) {
    provisioning.hidden = false;
  }
  const refreshIdentityStatus = async (): Promise<void> => {
    const status = await androidPlatform.identityStatus();
    if (identityStatus !== null) {
      identityStatus.textContent = [
        `Key: ${status.keyPresent ? "present" : "missing"}`,
        `non-exportable: ${status.nonExportable ? "yes" : "no"}`,
        `certificate: ${status.certificateInstalled ? "installed" : "missing"}`,
      ].join(" / ");
    }
  };
  void refreshIdentityStatus();
  root.querySelector<HTMLButtonElement>("[data-create-csr]")
    ?.addEventListener("click", () => {
      void (async () => {
        try {
          const request = await androidPlatform.createEnrollmentRequest();
          if (csr !== null) {
            csr.value = request.csrPem;
          }
          if (identityStatus !== null) {
            identityStatus.textContent = `CSR SHA-256: ${request.csrSha256}`;
          }
        } catch (error) {
          if (identityStatus !== null) {
            identityStatus.textContent = error instanceof Error
              ? error.message
              : "CSR generation failed";
          }
        }
      })();
    });
  root.querySelector<HTMLButtonElement>("[data-install-chain]")
    ?.addEventListener("click", () => {
      void (async () => {
        try {
          await androidPlatform.installCertificateChain(
            nodeCertificate?.value ?? "",
            authorityCertificate?.value ?? "",
          );
          await refreshIdentityStatus();
        } catch (error) {
          if (identityStatus !== null) {
            identityStatus.textContent = error instanceof Error
              ? error.message
              : "Certificate installation failed";
          }
        }
      })();
    });
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") {
    void (async () => {
      await conversation?.end();
      await node.suspend();
      showSnapshot();
    })();
    viewport.suspend();
  } else {
    viewport.resume();
    void (async () => {
      await node.resume();
      showSnapshot();
    })();
  }
});
