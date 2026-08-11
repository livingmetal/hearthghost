import { Capacitor } from "@capacitor/core";

import "./styles.css";
import { AttentionController } from "./attention/controller.js";
import { CharacterExperienceController } from "./character/experience.js";
import { loadCharacterRenderer } from "./character/renderer-loader.js";
import { CharacterViewport } from "./character/viewport.js";
import { TextConversationController } from "./conversation/controller.js";
import { BrowserDevelopmentNodePlatform } from "./node/browser-platform.js";
import {
  ANDROID_CREDENTIAL_REFERENCE,
  AndroidNodePlatform,
} from "./node/android-platform.js";
import { ClientNode } from "./node/client-node.js";
import type { NodePlatformPort } from "./node/platform.js";
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
const NOTICE_TO_LISTEN_MILLIS = 220;

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
    <header class="top-bar">
      <div class="brand-lockup" aria-label="HearthGhost">
        <span class="brand-mark" aria-hidden="true"></span>
        <span class="brand-name">HearthGhost</span>
      </div>
      <div class="top-actions">
        <button class="quiet-button" type="button" data-connect>Connect</button>
        <details class="system-status">
          <summary>System</summary>
          <div class="status-bar" aria-label="Privacy and security status">
            <span data-node-status>Node: disconnected</span>
            <span data-attention-status>Attention: sleeping</span>
            <span>Camera: denied</span>
            <span data-microphone-status>Microphone: inactive</span>
            <span data-speech-status>Speech: text only</span>
            <span>Cloud media: denied</span>
          </div>
        </details>
      </div>
    </header>

    <section class="character-stage" aria-label="HearthGhost character and response">
      <section class="character-viewport" aria-label="Character viewport"></section>
      <div class="response-layer">
        <output class="response" data-response aria-live="polite"></output>
      </div>
    </section>

    <section class="interaction-panel">
      <p class="notice" data-notice>Secure text transport is disconnected.</p>
      <div class="quick-actions" aria-label="Quick message templates">
        <button type="button" class="chip" data-template="메모해: ">Memo</button>
        <button type="button" class="chip" data-template="할 일: ">Todo</button>
        <button type="button" class="chip" data-template="알림 목록">Reminders</button>
      </div>
      <form class="text-row" data-conversation>
        <label class="sr-only" for="message">Conversation</label>
        <button class="wake-button" type="button" data-wake>Wake</button>
        <input id="message" autocomplete="off" enterkeyhint="send" placeholder="Type to Ghost" />
        <button class="speak-button" type="button" data-speak disabled>Speak</button>
        <button class="send-button" type="submit" data-send disabled>Send</button>
      </form>
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
const messageInput = root.querySelector<HTMLInputElement>("#message");
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
const character = new CharacterExperienceController(viewport);
const conversation = androidPlatform === null
  ? null
  : new TextConversationController(
      node,
      androidPlatform,
      (event) => character.presentServerEvent(event),
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
  wakeButton?.classList.toggle("is-awake", attentionSnapshot.state === "engaged");
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
    character.beginSpeaking();
    await voiceOutput.speak(text, VOICE_LOCALE);
    character.engage();
    showSnapshot();
    return true;
  } catch {
    character.showConcern();
    await refreshVoiceStatus();
    return false;
  }
}

connectButton?.addEventListener("click", () => {
  void (async () => {
    try {
      await node.connect({
        kind: "platform-managed",
        reference: androidPlatform === null
          ? "not-provisioned"
          : ANDROID_CREDENTIAL_REFERENCE,
      });
      const snapshot = node.snapshot();
      showSnapshot();
      if (snapshot.error !== null) {
        character.showConcern();
        if (notice !== null) {
          notice.textContent = snapshot.error;
        }
      } else if (notice !== null) {
        if (node.canUseCapability("conversation.text")) {
          character.acknowledgeSuccess();
          notice.textContent = "Secure Node ready. Touch Wake before conversation.";
        } else {
          character.showConcern();
          notice.textContent = "Authenticated, but explicit trust and conversation grant are required.";
        }
      }
    } catch (error) {
      character.showConcern();
      showSnapshot();
      if (notice !== null) {
        notice.textContent = error instanceof Error ? error.message : "Secure connection failed";
      }
    }
  })();
});

wakeButton?.addEventListener("click", () => {
  if (!node.canUseCapability("conversation.text")) {
    character.showConcern();
    if (notice !== null) {
      notice.textContent = "Connect a trusted Node with conversation.text grant first.";
    }
    return;
  }
  attention.wakeByTouch();
  character.wakeByTouch();
  window.setTimeout(() => {
    if (
      attention.canAcceptConversationInput()
      && viewport.snapshot().state === "noticing"
    ) {
      character.beginListening();
    }
  }, NOTICE_TO_LISTEN_MILLIS);
  showSnapshot();
  if (notice !== null) {
    notice.textContent = "Ghost noticed you. Address text or start local speech.";
  }
  messageInput?.focus();
});

for (const templateButton of root.querySelectorAll<HTMLButtonElement>("[data-template]")) {
  templateButton.addEventListener("click", () => {
    if (messageInput === null) {
      return;
    }
    messageInput.value = templateButton.dataset.template ?? "";
    messageInput.focus();
  });
}

speakButton?.addEventListener("click", () => {
  void (async () => {
    if (
      voiceInput === null
      || voiceConversation === null
      || !attention.canAcceptConversationInput()
    ) {
      character.showConcern();
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
      character.beginListening();
      await voiceInput.start(VOICE_LOCALE);
      voiceStatus = { ...voiceStatus, listening: true };
      showSnapshot();
      if (notice !== null) {
        notice.textContent = "Listening locally. Raw microphone audio is not sent to Core or cloud.";
      }
    } catch (error) {
      character.showConcern();
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
    if (conversation === null || messageInput === null) {
      character.showConcern();
      if (notice !== null) {
        notice.textContent = "Native text transport is unavailable.";
      }
      return;
    }
    if (!attention.canAcceptConversationInput()) {
      character.sleep();
      showSnapshot();
      if (notice !== null) {
        notice.textContent = "Ghost is sleeping. Use Wake before sending text.";
      }
      return;
    }
    try {
      if (conversation.snapshot().conversationSessionId === null) {
        await conversation.open();
      }
      character.beginThinking();
      const snapshot = await conversation.submit(messageInput.value);
      attention.recordAddressedActivity();
      showSnapshot();
      if (response !== null) {
        response.textContent = snapshot.responseText ?? "";
      }
      character.engage();
      if (notice !== null) {
        notice.textContent = "Conversation active. Attention timeout extended.";
      }
      messageInput.value = "";
    } catch (error) {
      character.showConcern();
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
      character.beginThinking();
      try {
        const snapshot = await voiceConversation.acceptTranscript(event);
        const reply = snapshot.responseText ?? "";
        if (response !== null) {
          response.textContent = reply;
        }
        const spoken = reply !== "" && await speakReplyLocally(reply);
        if (!spoken) {
          character.engage();
        }
        if (notice !== null) {
          notice.textContent = spoken
            ? "Reply spoken using an embedded Android voice."
            : "Local TTS unavailable. Reply remains text only.";
        }
      } catch (error) {
        character.showConcern();
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
      character.showConcern();
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
          character.showConcern();
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
          character.acknowledgeSuccess();
          await refreshIdentityStatus();
        } catch (error) {
          character.showConcern();
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
  character.sleep();
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
    character.sleep();
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
