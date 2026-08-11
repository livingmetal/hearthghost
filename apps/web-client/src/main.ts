import { Capacitor } from "@capacitor/core";

import "./styles.css";
import { AttentionController } from "./attention/controller.js";
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
import {
  AndroidVoiceInput,
  type VoiceInputStatus,
} from "./voice/android-voice.js";
import {
  AndroidVoiceOutput,
  type VoiceOutputStatus,
} from "./voice/android-tts.js";
import { VoiceConversationController } from "./voice/controller.js";

const ATTENTION_TIMEOUT_MILLIS = 20_000;
const VOICE_LOCALE = "ko-KR";

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
const attention = new AttentionController(ATTENTION_TIMEOUT_MILLIS);
const voiceInput = androidPlatform === null ? null : new AndroidVoiceInput();
const voiceOutput = androidPlatform === null ? null : new AndroidVoiceOutput();
let voiceStatus: VoiceInputStatus | null = null;
let ttsStatus: VoiceOutputStatus | null = null;

root.innerHTML = `
  <main class="app-shell">
    <header class="status-bar" aria-label="Privacy and security status">
      <span data-node-status>Node: disconnected</span>
      <span data-attention-status>Attention: sleeping</span>
      <span>Camera: denied</span>
      <span data-microphone-status>Microphone: inactive</span>
      <span data-speech-status>Speech: text only</span>
      <span>Cloud media: denied</span>
    </header>
    <section class="character-viewport" aria-label="Character viewport">
    </section>
    <section class="interaction-panel">
      <label for="message">Conversation</label>
      <form class="text-row" data-conversation>
        <input id="message" autocomplete="off" placeholder="Touch wake, then type or speak" />
        <button type="button" data-connect>Connect securely</button>
        <button type="button" data-wake>Wake Ghost</button>
        <button type="button" data-speak disabled>Speak</button>
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
const wakeButton = root.querySelector<HTMLButtonElement>("[data-wake]");
const speakButton = root.querySelector<HTMLButtonElement>("[data-speak]");
const nodeStatus = root.querySelector<HTMLElement>("[data-node-status]");
const attentionStatus = root.querySelector<HTMLElement>("[data-attention-status]");
const microphoneStatus = root.querySelector<HTMLElement>("[data-microphone-status]");
const speechStatus = root.querySelector<HTMLElement>("[data-speech-status]");
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
const voiceConversation = conversation === null
  ? null
  : new VoiceConversationController(attention, conversation);

function showSnapshot(): void {
  const snapshot = node.snapshot();
  const attentionSnapshot = attention.snapshot();
  if (nodeStatus !== null) {
    nodeStatus.textContent = `Node: ${snapshot.connection} / ${snapshot.trust}`;
  }
  if (attentionStatus !== null) {
    const remainingSeconds = Math.ceil(attentionSnapshot.remainingMillis / 1_000);
    attentionStatus.textContent = attentionSnapshot.state === "engaged"
      ? `Attention: engaged (${remainingSeconds}s)`
      : "Attention: sleeping";
  }
  if (microphoneStatus !== null) {
    if (voiceStatus === null) {
      microphoneStatus.textContent = voiceInput === null
        ? "Microphone: unavailable"
        : "Microphone: inactive";
    } else if (!voiceStatus.onDeviceAvailable) {
      microphoneStatus.textContent = "Microphone: on-device STT unavailable";
    } else if (voiceStatus.listening) {
      microphoneStatus.textContent = "Microphone: on-device listening";
    } else if (voiceStatus.permission !== "granted") {
      microphoneStatus.textContent = "Microphone: permission required";
    } else {
      microphoneStatus.textContent = "Microphone: ready / local only";
    }
  }
  if (speechStatus !== null) {
    speechStatus.textContent = ttsStatus?.initialized && ttsStatus.localVoiceAvailable
      ? "Speech: embedded TTS ready"
      : "Speech: text fallback";
  }
  const conversationAllowed = node.canUseCapability("conversation.text")
    && attentionSnapshot.state === "engaged";
  if (sendButton !== null) {
    sendButton.disabled = !conversationAllowed;
  }
  if (speakButton !== null) {
    speakButton.disabled = !conversationAllowed
      || voiceInput === null
      || voiceStatus?.onDeviceAvailable === false
      || voiceStatus?.listening === true;
  }
}

async function refreshVoiceStatus(): Promise<void> {
  if (voiceInput === null) {
    voiceStatus = null;
  } else {
    try {
      voiceStatus = await voiceInput.status();
    } catch {
      voiceStatus = null;
    }
  }
  if (voiceOutput === null) {
    ttsStatus = null;
  } else {
    try {
      ttsStatus = await voiceOutput.status(VOICE_LOCALE);
    } catch {
      ttsStatus = null;
    }
  }
  showSnapshot();
}

async function speakReplyLocally(text: string): Promise<boolean> {
  if (voiceOutput === null) {
    return false;
  }
  try {
    ttsStatus = await voiceOutput.status(VOICE_LOCALE);
    if (!ttsStatus.initialized || !ttsStatus.localVoiceAvailable) {
      showSnapshot();
      return false;
    }
    await voiceOutput.speak(text, VOICE_LOCALE);
    showSnapshot();
    return true;
  } catch {
    await refreshVoiceStatus();
    return false;
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
      ? "Authenticated and granted. Touch Wake Ghost before conversation."
      : "Authenticated, but explicit trust and conversation grant are required.";
  }
});

wakeButton?.addEventListener("click", () => {
  if (!node.canUseCapability("conversation.text")) {
    if (notice !== null) {
      notice.textContent = "Connect a trusted Node with conversation.text grant first.";
    }
    return;
  }
  attention.wakeByTouch();
  showSnapshot();
  if (notice !== null) {
    notice.textContent = "Ghost is listening for addressed text or speech.";
  }
  root.querySelector<HTMLInputElement>("#message")?.focus();
});

speakButton?.addEventListener("click", () => {
  void (async () => {
    if (
      voiceInput === null
      || voiceConversation === null
      || !attention.canAcceptConversationInput()
    ) {
      if (notice !== null) {
        notice.textContent = "Wake Ghost before starting on-device speech recognition.";
      }
      showSnapshot();
      return;
    }
    try {
      voiceStatus = await voiceInput.status();
      if (!voiceStatus.onDeviceAvailable) {
        throw new Error("This Android device has no on-device speech recognizer.");
      }
      if (voiceStatus.permission !== "granted") {
        voiceStatus = await voiceInput.requestMicrophonePermission();
        showSnapshot();
        if (notice !== null) {
          notice.textContent = "Microphone permission granted. Tap Speak again to begin local recognition.";
        }
        return;
      }
      await voiceOutput?.stop();
      await voiceInput.start(VOICE_LOCALE);
      voiceStatus = { ...voiceStatus, listening: true };
      showSnapshot();
      if (notice !== null) {
        notice.textContent = "Listening locally. Raw microphone audio is not sent to Core or cloud.";
      }
    } catch (error) {
      await refreshVoiceStatus();
      if (notice !== null) {
        notice.textContent = error instanceof Error ? error.message : "Voice input failed";
      }
    }
  })();
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
    if (!attention.canAcceptConversationInput()) {
      showSnapshot();
      if (notice !== null) {
        notice.textContent = "Ghost is sleeping. Use Wake Ghost before sending text.";
      }
      return;
    }
    try {
      if (conversation.snapshot().conversationSessionId === null) {
        await conversation.open();
      }
      const snapshot = await conversation.submit(input.value);
      attention.recordAddressedActivity();
      showSnapshot();
      if (response !== null) {
        response.textContent = snapshot.responseText ?? "";
      }
      if (notice !== null) {
        notice.textContent = "Conversation active. Attention timeout extended.";
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

if (voiceInput !== null && voiceConversation !== null) {
  void voiceInput.onTranscript((event) => {
    void (async () => {
      voiceStatus = voiceStatus === null ? null : { ...voiceStatus, listening: false };
      try {
        const snapshot = await voiceConversation.acceptTranscript(event);
        const reply = snapshot.responseText ?? "";
        if (response !== null) {
          response.textContent = reply;
        }
        const spoken = reply !== "" && await speakReplyLocally(reply);
        if (notice !== null) {
          notice.textContent = spoken
            ? `On-device transcript accepted and reply spoken locally: ${event.text}`
            : `On-device transcript accepted; local TTS unavailable, showing text: ${event.text}`;
        }
      } catch (error) {
        if (notice !== null) {
          notice.textContent = error instanceof Error ? error.message : "Voice transcript rejected";
        }
      } finally {
        await refreshVoiceStatus();
      }
    })();
  });
  void voiceInput.onError((event) => {
    void (async () => {
      await refreshVoiceStatus();
      if (notice !== null) {
        notice.textContent = `Voice input stopped: ${event.reason}`;
      }
    })();
  });
  void refreshVoiceStatus();
}

if (androidPlatform !== null) {
  const provisioning = root.querySelector<HTMLDetailsElement>("[data-provision]");
  const identityStatus = root.querySelector<HTMLElement>("[data-identity-status]");
  const csr = root.querySelector<HTMLTextAreaElement>("[data-csr]");
  const nodeCertificate = root.querySelector<HTMLTextAreaElement>("[data-node-certificate]");
  const authorityCertificate = root.querySelector<HTMLTextAreaElement>("[data-authority-certificate]");
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

const attentionTimer = window.setInterval(() => {
  if (!attention.expireIfIdle()) {
    showSnapshot();
    return;
  }
  showSnapshot();
  void voiceInput?.cancel();
  void voiceOutput?.stop();
  void conversation?.end();
  if (notice !== null) {
    notice.textContent = "Attention timed out. Ghost returned to sleep.";
  }
}, 1_000);

window.addEventListener("pagehide", () => window.clearInterval(attentionTimer), {
  once: true,
});

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") {
    attention.sleep();
    void (async () => {
      await voiceInput?.cancel();
      await voiceOutput?.stop();
      await conversation?.end();
      await node.suspend();
      await refreshVoiceStatus();
      showSnapshot();
    })();
    viewport.suspend();
  } else {
    viewport.resume();
    void (async () => {
      await node.resume();
      await refreshVoiceStatus();
      showSnapshot();
    })();
  }
});
