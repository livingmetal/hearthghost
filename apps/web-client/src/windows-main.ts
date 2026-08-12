import "./styles.css";
import "./persona.css";
import "./history.css";
import "./windows.css";

import {
  characterById,
  type HearthGhostCharacterDefinition,
} from "./character/catalog.js";
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
import { ClientNode } from "./node/client-node.js";
import {
  WINDOWS_CREDENTIAL_REFERENCE,
  WindowsNodePlatform,
} from "./node/windows-platform.js";
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
  loadActivePersonaId,
  loadPersonaProfiles,
  newCustomPersonaId,
  personaProfileCommand,
  saveActivePersonaId,
  saveCustomPersonaProfile,
  type PersonaProfilePreset,
} from "./options/persona-profiles.js";
import {
  RESPONSE_REVEAL_DONE_EVENT,
  type ResponseRevealDetail,
} from "./response-reveal.js";
import { WindowsWebViewBridge, windowsWebViewHost } from "./windows/webview-bridge.js";

const root = document.querySelector<HTMLDivElement>("#app");
if (root === null) {
  throw new Error("HearthGhost Windows client root is missing");
}

const host = windowsWebViewHost();
if (host === null) {
  root.innerHTML = `<main class="windows-host-error"><h1>HearthGhost</h1><p>This page must run inside the reviewed Windows WebView2 host.</p></main>`;
  throw new Error("Windows WebView2 native host is unavailable");
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

root.innerHTML = `
  <main class="app-shell windows-shell">
    <header class="top-bar">
      <div class="brand-lockup" aria-label="HearthGhost">
        <span class="brand-mark" aria-hidden="true"></span>
        <span class="brand-name">HearthGhost · Windows</span>
      </div>
      <div class="top-actions">
        <button class="quiet-button" type="button" data-connect>Connect</button>
        ${characterOptionsMarkup(startupCharacter.id, personaProfiles, activePersonaId)}
      </div>
    </header>

    <section class="character-stage windows-character-stage" aria-label="HearthGhost character and response">
      <div class="character-identity" aria-live="polite">
        <span class="character-identity-label">Persona</span>
        <strong data-character-name>${activePersona.name}</strong>
      </div>
      <section class="character-viewport" aria-label="${startupCharacter.name} character viewport"></section>
      <div class="response-layer">
        <output class="response" data-response aria-live="polite"></output>
      </div>
    </section>

    <section class="interaction-panel windows-interaction-panel">
      <p class="notice" data-notice>Windows native mTLS transport is disconnected.</p>
      <div class="windows-node-status" data-node-status>Node: disconnected</div>
      <section class="session-history" data-session-history aria-label="Ephemeral conversation history"></section>
      <form class="text-row windows-text-row" data-conversation>
        <label class="sr-only" for="message">Conversation</label>
        <input id="message" autocomplete="off" enterkeyhint="send" placeholder="영희나 철수에게 말하기" />
        <button class="send-button" type="submit" data-send disabled>Send</button>
      </form>
    </section>
  </main>
`;

const nativeBridge = new WindowsWebViewBridge(host);
const platform = new WindowsNodePlatform(nativeBridge);
const node = new ClientNode(platform);
const viewportElement = requireElement<HTMLElement>(".character-viewport");
let viewport = new CharacterViewport(
  viewportElement,
  await loadCharacterRenderer("vrm", startupCharacter.assetUrl),
);
let renderedCharacterId: string | null = startupCharacter.id;
let initialVrmFallback = false;
try {
  await viewport.mount();
} catch {
  viewport.dispose();
  viewport = new CharacterViewport(viewportElement, await loadCharacterRenderer("dom"));
  await viewport.mount();
  renderedCharacterId = null;
  initialVrmFallback = true;
}
const character = new CharacterExperienceController(viewport);
const conversation = new TextConversationController(
  node,
  platform,
  (event) => character.presentServerEvent(event),
);
const history = new EphemeralSessionHistory();
const historyView = new SessionHistoryView(requireElement<HTMLElement>("[data-session-history]"));

const connectButton = requireElement<HTMLButtonElement>("[data-connect]");
const sendButton = requireElement<HTMLButtonElement>("[data-send]");
const form = requireElement<HTMLFormElement>("[data-conversation]");
const input = requireElement<HTMLInputElement>("#message");
const notice = requireElement<HTMLElement>("[data-notice]");
const response = requireElement<HTMLOutputElement>("[data-response]");
const nodeStatus = requireElement<HTMLElement>("[data-node-status]");
const characterName = requireElement<HTMLElement>("[data-character-name]");
const characterOptions = requireCharacterOptions(root);
writePersonaForm(characterOptions, activePersona);
let profileApplySequence = 0;

if (initialVrmFallback) {
  notice.textContent = `${startupCharacter.sample} VRM could not be loaded. The fallback character is active.`;
}

function showNodeSnapshot(): void {
  const snapshot = node.snapshot();
  nodeStatus.textContent = `Node: ${snapshot.connection} / ${snapshot.trust}`;
  sendButton.disabled = !node.canUseCapability("conversation.text");
  connectButton.textContent = snapshot.connection === "connected" ? "Reconnect" : "Connect";
}

async function ensureConversationOpen(): Promise<void> {
  if (conversation.snapshot().conversationSessionId !== null) {
    return;
  }
  const opened = await conversation.open();
  await applyCharacterProfile(opened.characterProfile);
  await synchronizeActivePersonaToCore();
}

function rememberCharacter(selected: HearthGhostCharacterDefinition): boolean {
  preferredCharacterId = selected.id;
  selectCharacterOption(characterOptions, selected.id);
  const saved = savePreferredCharacterId(preferenceStorage, selected.id);
  setCharacterOptionsStatus(
    characterOptions,
    saved
      ? "Saved on this device. Core persona syncs when a trusted conversation is available."
      : "Character changed for this run, but persistent browser storage is unavailable.",
  );
  return saved;
}

async function displayCharacter(selected: HearthGhostCharacterDefinition): Promise<void> {
  selectCharacterOption(characterOptions, selected.id);
  viewportElement.setAttribute("aria-label", `${selected.name} character viewport`);
  if (selected.id === renderedCharacterId) {
    return;
  }
  const sequence = ++profileApplySequence;
  try {
    const renderer = await loadCharacterRenderer("vrm", selected.assetUrl);
    if (sequence !== profileApplySequence) {
      renderer.dispose();
      return;
    }
    await viewport.replaceRenderer(renderer);
    renderedCharacterId = selected.id;
    notice.textContent = `${selected.name} (${selected.sample}) loaded locally.`;
  } catch {
    if (sequence === profileApplySequence) {
      notice.textContent = `${selected.name} profile applied. VRM unavailable, using the safe fallback renderer.`;
    }
  }
}

async function applyCharacterProfile(
  profile: CharacterDisplayProfile | null,
): Promise<void> {
  if (profile === null) {
    return;
  }
  characterName.textContent = profile.name;
}

async function synchronizeActivePersonaToCore(): Promise<void> {
  const synchronized = await conversation.submit(personaProfileCommand(activePersona));
  await applyCharacterProfile(synchronized.characterProfile);
}

async function submitText(text: string): Promise<void> {
  const normalized = text.trim();
  if (normalized === "") {
    return;
  }
  response.textContent = "";
  await ensureConversationOpen();
  character.beginThinking();
  const snapshot = await conversation.submit(normalized);
  await applyCharacterProfile(snapshot.characterProfile);
  const reply = snapshot.responseText ?? "";
  if (reply !== "") {
    historyView.render(history.append("user", normalized));
    historyView.render(history.append("assistant", reply));
    character.beginSpeaking();
    response.textContent = reply;
  } else {
    character.engage();
  }
  notice.textContent = "Conversation active over Windows native mTLS.";
}

const onResponseRevealDone = (event: CustomEvent<ResponseRevealDetail>): void => {
  if (
    viewport.snapshot().state === "speaking"
    && response.textContent?.trim() === event.detail.text.trim()
  ) {
    character.engage();
  }
};
window.addEventListener(RESPONSE_REVEAL_DONE_EVENT, onResponseRevealDone as EventListener);

connectButton.addEventListener("click", () => {
  void (async () => {
    history.clear();
    historyView.clear();
    response.textContent = "";
    conversation.reset();
    try {
      character.wakeByTouch();
      const snapshot = await node.connect({
        kind: "platform-managed",
        reference: WINDOWS_CREDENTIAL_REFERENCE,
      });
      showNodeSnapshot();
      if (snapshot.error !== null) {
        character.showConcern();
        notice.textContent = snapshot.error;
        return;
      }
      if (!node.canUseCapability("conversation.text")) {
        character.showConcern();
        notice.textContent = "Authenticated Windows Node needs explicit trust and conversation.text grant.";
        return;
      }
      await ensureConversationOpen();
      character.acknowledgeSuccess();
      notice.textContent = `${characterName.textContent} is active over Windows native mTLS.`;
      input.focus();
    } catch (error) {
      character.showConcern();
      showNodeSnapshot();
      notice.textContent = error instanceof Error ? error.message : "Windows Node connection failed";
    }
  })();
});

characterOptions.appearanceSelect.addEventListener("change", () => {
  void (async () => {
    const selected = characterById(characterOptions.appearanceSelect.value);
    if (selected === null) {
      selectCharacterOption(characterOptions, preferredCharacterId);
      return;
    }
    const saved = rememberCharacter(selected);
    try {
      await displayCharacter(selected);
      if (!node.canUseCapability("conversation.text")) {
        setCharacterOptionsStatus(
          characterOptions,
          saved
            ? "Appearance saved on this device."
            : "Character changed for this run, but persistent browser storage is unavailable.",
        );
        notice.textContent = `${selected.name} appearance will be used at the next launch.`;
        return;
      }
      character.acknowledgeSuccess();
      setCharacterOptionsStatus(characterOptions, "Appearance saved on this device.");
      notice.textContent = `${selected.name} VRM and local voice are active. Persona was not changed.`;
    } catch (error) {
      character.showConcern();
      setCharacterOptionsStatus(
        characterOptions,
        "Appearance changed for this run; persistent storage is unavailable.",
      );
      notice.textContent = error instanceof Error
        ? `Character saved locally; Core sync pending: ${error.message}`
        : "Character saved locally; Core sync pending.";
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
  saveActivePersonaId(preferenceStorage, personaProfiles, activePersonaId);
  populatePersonaOptions(characterOptions, personaProfiles, activePersonaId);
  writePersonaForm(characterOptions, activePersona);
  void applySelectedPersona();
});

async function applySelectedPersona(): Promise<void> {
  characterName.textContent = activePersona.name;
  if (!node.canUseCapability("conversation.text")) {
    setPersonaOptionsStatus(characterOptions, "Saved locally. Connect a trusted Node to apply it to Core.");
    return;
  }
  try {
    if (conversation.snapshot().conversationSessionId === null) {
      await ensureConversationOpen();
    } else {
      await synchronizeActivePersonaToCore();
    }
    character.acknowledgeSuccess();
    setPersonaOptionsStatus(characterOptions, "Saved locally and applied to Core.");
    notice.textContent = `${activePersona.name} persona is active; appearance is unchanged.`;
  } catch (error) {
    character.showConcern();
    setPersonaOptionsStatus(characterOptions, error instanceof Error
      ? `Saved locally; Core apply pending: ${error.message}`
      : "Saved locally; Core apply pending.");
  }
}

function requirePersona(id: string): PersonaProfilePreset {
  const profile = personaProfiles.find((candidate) => candidate.id === id) ?? personaProfiles[0];
  if (profile === undefined) {
    throw new Error("HearthGhost has no persona profiles");
  }
  return profile;
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  void (async () => {
    try {
      await submitText(input.value);
      input.value = "";
      input.focus();
    } catch (error) {
      character.showConcern();
      notice.textContent = error instanceof Error ? error.message : "Conversation failed";
    }
  })();
});

window.addEventListener("pagehide", () => {
  window.removeEventListener(RESPONSE_REVEAL_DONE_EVENT, onResponseRevealDone as EventListener);
  history.clear();
  historyView.clear();
  nativeBridge.dispose();
  viewport.dispose();
  void node.disconnect();
}, { once: true });

showNodeSnapshot();

function requireElement<T extends Element>(selector: string): T {
  const element = root?.querySelector<T>(selector) ?? null;
  if (element === null) {
    throw new Error(`Windows client element is missing: ${selector}`);
  }
  return element;
}
