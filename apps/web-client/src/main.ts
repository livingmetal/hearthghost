import { Capacitor } from "@capacitor/core";

import "./styles.css";
import "./persona.css";
import "./history.css";
import { AttentionController } from "./attention/controller.js";
import {
  characterById,
  type HearthGhostCharacterDefinition,
} from "./character/catalog.js";
import { DialoguePerformanceController } from "./character/dialogue-performance.js";
import { CharacterExperienceController } from "./character/experience.js";
import {
  browserCharacterPreferenceStorage,
  DEFAULT_CHARACTER_ID,
  loadPreferredCharacterId,
  savePreferredCharacterId,
} from "./character/preferences.js";
import type { CharacterDisplayProfile } from "./character/profile.js";
import { loadCharacterRenderer } from "./character/renderer-loader.js";
import { CharacterViewport } from "./character/viewport.js";
import { EphemeralSessionHistory, SessionHistoryView } from "./conversation/history.js";
import { TextConversationController } from "./conversation/controller.js";
import { BrowserDevelopmentNodePlatform } from "./node/browser-platform.js";
import {
  ANDROID_CREDENTIAL_REFERENCE,
  AndroidNodePlatform,
} from "./node/android-platform.js";
import { ClientNode } from "./node/client-node.js";
import type { NodePlatformPort } from "./node/platform.js";
import {
  characterOptionsMarkup,
  populatePersonaOptions,
  readPersonaForm,
  requireCharacterOptions,
  selectCharacterOption,
  setCharacterOptionsStatus,
  setPersonaOptionsStatus,
  writePersonaForm,
} from "./options/character-options.js";
import {
  createCustomPersonaProfile,
  deleteCustomPersonaProfile,
  findMatchingPersonaProfile,
  loadActivePersonaId,
  loadPersonaProfiles,
  newCustomPersonaId,
  personaProfileCommand,
  parseServerPersonaState,
  saveActivePersonaId,
  saveCustomPersonaProfile,
  SERVER_PERSONA_QUERY,
  type PersonaProfilePreset,
} from "./options/persona-profiles.js";
import {
  AndroidVoiceInput,
  type VoiceInputStatus,
} from "./voice/android-voice.js";
import {
  AndroidVoiceOutput,
  type VoiceOutputStatus,
  type VoiceProfileId,
} from "./voice/android-tts.js";
import { VoiceConversationController } from "./voice/controller.js";

const ATTENTION_TIMEOUT_MILLIS = 20_000;
const VOICE_LOCALE = "ko-KR";
const NOTICE_TO_LISTEN_MILLIS = 220;

const root = document.querySelector<HTMLDivElement>("#app");
if (root === null) {
  throw new Error("HearthGhost client root is missing");
}

const preferenceStorage = browserCharacterPreferenceStorage();
let preferredCharacterId = loadPreferredCharacterId(preferenceStorage);
const startupCharacter = characterById(preferredCharacterId)
  ?? characterById(DEFAULT_CHARACTER_ID);
if (startupCharacter === null) {
  throw new Error("HearthGhost has no bundled default character");
}
let personaProfiles = loadPersonaProfiles(preferenceStorage);
let activePersonaId = loadActivePersonaId(preferenceStorage, personaProfiles, startupCharacter.id);
let activePersona = requirePersona(activePersonaId);
let creatingPersona = false;

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
let activeCharacter: HearthGhostCharacterDefinition | null = startupCharacter;
let renderedCharacterId: string | null = startupCharacter.id;
let initialVrmFallback = false;

root.innerHTML = `
  <main class="app-shell">
    <header class="top-bar">
      <div class="brand-lockup" aria-label="HearthGhost">
        <span class="brand-mark" aria-hidden="true"></span>
        <span class="brand-name">HearthGhost</span>
      </div>
      <div class="top-actions">
        <button class="quiet-button" type="button" data-connect>Connect</button>
        ${characterOptionsMarkup(startupCharacter.id, personaProfiles, activePersonaId)}
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
      <div class="character-identity" aria-live="polite">
        <span class="character-identity-label">Persona</span>
        <strong data-character-name>${activePersona.name}</strong>
      </div>
      <section class="character-viewport" aria-label="${startupCharacter.name} character viewport"></section>
      <div class="response-layer">
        <output class="response" data-response aria-live="polite"></output>
      </div>
    </section>

    <section class="interaction-panel">
      <p class="notice" data-notice>Secure text transport is disconnected.</p>
      <section class="session-history" data-session-history aria-label="Ephemeral conversation history"></section>
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
const characterName = root.querySelector<HTMLElement>("[data-character-name]");
const characterOptions = requireCharacterOptions(root);
writePersonaForm(characterOptions, activePersona);
const notice = root.querySelector<HTMLElement>("[data-notice]");
const response = root.querySelector<HTMLOutputElement>("[data-response]");
const form = root.querySelector<HTMLFormElement>("[data-conversation]");
const sendButton = root.querySelector<HTMLButtonElement>("[data-send]");
const messageInput = root.querySelector<HTMLInputElement>("#message");
const historyHost = root.querySelector<HTMLElement>("[data-session-history]");
const viewportElement = root.querySelector<HTMLElement>(".character-viewport");
if (historyHost === null) {
  throw new Error("Session history element is missing");
}
if (viewportElement === null) {
  throw new Error("CharacterViewport element is missing");
}
const characterViewportElement = viewportElement;
selectCharacterOption(characterOptions, preferredCharacterId);
const history = new EphemeralSessionHistory();
const historyView = new SessionHistoryView(historyHost);

let viewport = new CharacterViewport(
  characterViewportElement,
  await loadCharacterRenderer("vrm", startupCharacter.assetUrl),
);
try {
  await viewport.mount();
} catch {
  viewport.dispose();
  viewport = new CharacterViewport(
    characterViewportElement,
    await loadCharacterRenderer("dom"),
  );
  await viewport.mount();
  renderedCharacterId = null;
  initialVrmFallback = true;
}
viewport.setExpressionStyle(activePersona.expressionStyle);

const character = new CharacterExperienceController(viewport);
const dialoguePerformance = new DialoguePerformanceController(character);
dialoguePerformance.install();
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

if (initialVrmFallback && notice !== null) {
  notice.textContent = `${startupCharacter.sample} VRM could not be loaded. The fallback character is active.`;
}

function currentVoiceProfile(): VoiceProfileId {
  return activeCharacter?.voice.id ?? "default";
}

function setCharacterSettingStatus(message: string): void {
  setCharacterOptionsStatus(characterOptions, message);
}

function rememberCharacter(characterDefinition: HearthGhostCharacterDefinition): void {
  preferredCharacterId = characterDefinition.id;
  const saved = savePreferredCharacterId(preferenceStorage, characterDefinition.id);
  setCharacterSettingStatus(saved
    ? "Appearance saved on this device."
    : "Character changed for this run, but persistent browser storage is unavailable.");
}

async function displayCharacter(
  selected: HearthGhostCharacterDefinition,
  persistPreference: boolean,
): Promise<void> {
  if (persistPreference) {
    rememberCharacter(selected);
  }
  activeCharacter = selected;
  selectCharacterOption(characterOptions, selected.id);
  characterViewportElement.setAttribute("aria-label", `${selected.name} character viewport`);

  if (renderedCharacterId !== selected.id) {
    try {
      await viewport.replaceRenderer(await loadCharacterRenderer("vrm", selected.assetUrl));
      renderedCharacterId = selected.id;
    } catch {
      if (notice !== null) {
        notice.textContent = `${selected.sample} VRM could not be loaded. The previous renderer remains active.`;
      }
    }
  }
  await refreshVoiceStatus();
}

async function applyCharacterProfile(
  profile: CharacterDisplayProfile | null,
): Promise<void> {
  if (profile === null) {
    return;
  }
  if (characterName !== null) characterName.textContent = profile.name;
}

function adoptServerPersona(serverPersona: PersonaProfilePreset): void {
  let selected = findMatchingPersonaProfile(personaProfiles, serverPersona);
  if (selected === null) {
    selected = serverPersona;
    try {
      personaProfiles = saveCustomPersonaProfile(preferenceStorage, personaProfiles, selected);
    } catch {
      personaProfiles = Object.freeze([
        ...personaProfiles.filter((candidate) => candidate.id !== selected?.id),
        selected,
      ]);
    }
  }
  activePersonaId = selected.id;
  activePersona = selected;
  viewport.setExpressionStyle(selected.expressionStyle);
  saveActivePersonaId(preferenceStorage, personaProfiles, selected.id);
  populatePersonaOptions(characterOptions, personaProfiles, selected.id);
  writePersonaForm(characterOptions, selected);
  if (characterName !== null) characterName.textContent = selected.name;
}

async function hydratePersonaFromCore(): Promise<void> {
  if (conversation === null) return;
  const snapshot = await conversation.submit(SERVER_PERSONA_QUERY);
  const response = snapshot.responseText;
  if (response === null) throw new Error("Core omitted the active persona state");
  adoptServerPersona(parseServerPersonaState(response));
}

async function synchronizeActivePersonaToCore(): Promise<void> {
  if (conversation === null) {
    return;
  }
  const synchronized = await conversation.submit(personaProfileCommand(activePersona));
  await applyCharacterProfile(synchronized.characterProfile);
}

async function ensureConversationCharacter(): Promise<void> {
  if (conversation === null || conversation.snapshot().conversationSessionId !== null) {
    return;
  }
  const opened = await conversation.open();
  await applyCharacterProfile(opened.characterProfile);
  await hydratePersonaFromCore();
}

function currentCharacterName(): string {
  return characterName?.textContent?.trim() || "Ghost";
}

function appendHistory(role: "user" | "assistant", text: string): void {
  historyView.render(history.append(role, text));
}

function clearSessionHistory(): void {
  history.clear();
  historyView.clear();
}

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
    const profileLabel = activeCharacter?.name ?? "default";
    speechStatus.textContent = ttsStatus?.initialized && ttsStatus.localVoiceAvailable
      ? `Speech: ${profileLabel} embedded TTS ready`
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
      ttsStatus = await voiceOutput.status(VOICE_LOCALE, currentVoiceProfile());
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
    const voiceProfile = currentVoiceProfile();
    ttsStatus = await voiceOutput.status(VOICE_LOCALE, voiceProfile);
    if (!ttsStatus.initialized || !ttsStatus.localVoiceAvailable) {
      showSnapshot();
      return false;
    }
    await voiceOutput.speak(text, VOICE_LOCALE, voiceProfile);
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
    clearSessionHistory();
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
    notice.textContent = `${currentCharacterName()} noticed you. Address text or start local speech.`;
  }
  messageInput?.focus();
});

characterOptions.appearanceSelect.addEventListener("change", () => {
  void (async () => {
    const requested = characterById(characterOptions.appearanceSelect.value);
    if (requested === null) {
      selectCharacterOption(characterOptions, preferredCharacterId);
      return;
    }

    rememberCharacter(requested);
    try {
      await displayCharacter(requested, false);
      character.acknowledgeSuccess();
      setCharacterSettingStatus("Appearance saved on this device.");
      if (notice !== null) {
        notice.textContent = `${requested.name}: ${requested.sample} / local voice selected. Persona was not changed.`;
      }
      showSnapshot();
    } catch (error) {
      setCharacterSettingStatus(
        "Appearance changed for this run; persistent storage is unavailable.",
      );
      if (notice !== null) {
        notice.textContent = error instanceof Error
          ? `Character saved locally; Core sync pending: ${error.message}`
          : "Character saved locally; Core sync pending.";
      }
    }
  })();
});

characterOptions.personaSelect.addEventListener("change", () => {
  const selected = personaProfiles.find((profile) => profile.id === characterOptions.personaSelect.value);
  if (selected === undefined) {
    writePersonaForm(characterOptions, activePersona);
    return;
  }
  creatingPersona = false;
  activePersonaId = selected.id;
  activePersona = selected;
  viewport.setExpressionStyle(selected.expressionStyle);
  saveActivePersonaId(preferenceStorage, personaProfiles, selected.id);
  writePersonaForm(characterOptions, selected);
  void applySelectedPersona();
});

characterOptions.personaNew.addEventListener("click", () => {
  creatingPersona = true;
  characterOptions.personaSelect.value = "";
  characterOptions.personaName.value = "";
  characterOptions.personaHumor.value = "moderate";
  characterOptions.personaVerbosity.value = "normal";
  characterOptions.personaFormality.value = "casual";
  characterOptions.personaInitiative.value = "low";
  characterOptions.personaExpressionStyle.value = "balanced";
  characterOptions.personaDelete.disabled = true;
  setPersonaOptionsStatus(characterOptions, "Enter a name, then choose Save & apply.");
  characterOptions.personaName.focus();
});

characterOptions.personaSave.addEventListener("click", () => {
  try {
    const selected = personaProfiles.find((profile) => profile.id === characterOptions.personaSelect.value);
    const id = !creatingPersona && selected !== undefined && !selected.builtIn
      ? selected.id
      : newCustomPersonaId();
    const profile = createCustomPersonaProfile(id, readPersonaForm(characterOptions));
    personaProfiles = saveCustomPersonaProfile(preferenceStorage, personaProfiles, profile);
    activePersonaId = profile.id;
    activePersona = profile;
    viewport.setExpressionStyle(profile.expressionStyle);
    creatingPersona = false;
    saveActivePersonaId(preferenceStorage, personaProfiles, profile.id);
    populatePersonaOptions(characterOptions, personaProfiles, profile.id);
    writePersonaForm(characterOptions, profile);
    void applySelectedPersona();
  } catch (error) {
    setPersonaOptionsStatus(characterOptions, error instanceof Error ? error.message : "Persona could not be saved.");
  }
});

characterOptions.personaDelete.addEventListener("click", () => {
  const selected = personaProfiles.find((profile) => profile.id === characterOptions.personaSelect.value);
  if (selected === undefined || selected.builtIn) {
    return;
  }
  personaProfiles = deleteCustomPersonaProfile(preferenceStorage, personaProfiles, selected.id);
  activePersonaId = preferredCharacterId;
  activePersona = requirePersona(activePersonaId);
  viewport.setExpressionStyle(activePersona.expressionStyle);
  saveActivePersonaId(preferenceStorage, personaProfiles, activePersonaId);
  populatePersonaOptions(characterOptions, personaProfiles, activePersonaId);
  writePersonaForm(characterOptions, activePersona);
  void applySelectedPersona();
});

async function applySelectedPersona(): Promise<void> {
  viewport.setExpressionStyle(activePersona.expressionStyle);
  if (characterName !== null) {
    characterName.textContent = activePersona.name;
  }
  const canApply = conversation !== null
    && node.canUseCapability("conversation.text")
    && attention.canAcceptConversationInput();
  if (!canApply) {
    setPersonaOptionsStatus(characterOptions, "Draft cached locally. Connect and Wake to save it to Core.");
    return;
  }
  try {
    if (conversation.snapshot().conversationSessionId === null) {
      await ensureConversationCharacter();
    }
    await synchronizeActivePersonaToCore();
    attention.recordAddressedActivity();
    character.acknowledgeSuccess();
    setPersonaOptionsStatus(characterOptions, "Saved to Core and cached on this device.");
    if (notice !== null) {
      notice.textContent = `${activePersona.name} persona is active; appearance is unchanged.`;
    }
  } catch (error) {
    character.showConcern();
    setPersonaOptionsStatus(characterOptions, error instanceof Error
      ? `Draft cached locally; Core save pending: ${error.message}`
      : "Draft cached locally; Core save pending.");
  }
}

function requirePersona(id: string): PersonaProfilePreset {
  const profile = personaProfiles.find((candidate) => candidate.id === id) ?? personaProfiles[0];
  if (profile === undefined) {
    throw new Error("HearthGhost has no persona profiles");
  }
  return profile;
}

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
        notice.textContent = `Wake ${currentCharacterName()} before starting on-device speech recognition.`;
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
        notice.textContent = `${currentCharacterName()} is sleeping. Use Wake before sending text.`;
      }
      return;
    }
    const submittedText = messageInput.value.trim();
    try {
      await ensureConversationCharacter();
      character.beginThinking();
      const snapshot = await conversation.submit(submittedText);
      await applyCharacterProfile(snapshot.characterProfile);
      attention.recordAddressedActivity();
      showSnapshot();
      const reply = snapshot.responseText ?? "";
      if (reply !== "") {
        appendHistory("user", submittedText);
        appendHistory("assistant", reply);
      }
      if (response !== null) {
        response.textContent = reply;
      }
      if (reply === "") {
        character.engage();
      }
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
        await ensureConversationCharacter();
        const snapshot = await voiceConversation.acceptTranscript(event);
        await applyCharacterProfile(snapshot.characterProfile);
        const reply = snapshot.responseText ?? "";
        if (reply !== "") {
          appendHistory("user", event.text.trim());
          appendHistory("assistant", reply);
        }
        if (response !== null) {
          response.textContent = reply;
        }
        const spoken = reply !== "" && await speakReplyLocally(reply);
        if (!spoken && reply === "") {
          character.engage();
        }
        if (notice !== null) {
          notice.textContent = spoken
            ? `Reply spoken using the ${activeCharacter?.name ?? "default"} embedded Android voice profile.`
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
  clearSessionHistory();
  showSnapshot();
  void voiceInput?.cancel();
  void voiceOutput?.stop();
  void conversation?.end();
  if (notice !== null) {
    notice.textContent = `Attention timed out. ${currentCharacterName()} returned to sleep.`;
  }
}, 1_000);

window.addEventListener("pagehide", () => {
  window.clearInterval(attentionTimer);
  dialoguePerformance.dispose();
  clearSessionHistory();
}, {
  once: true,
});

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") {
    attention.sleep();
    character.sleep();
    clearSessionHistory();
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
