import "./styles.css";
import "./persona.css";
import "./history.css";
import "./windows.css";

import { CHARACTER_CATALOG, characterByName, selectionCommand } from "./character/catalog.js";
import { CharacterExperienceController } from "./character/experience.js";
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

root.innerHTML = `
  <main class="app-shell windows-shell">
    <header class="top-bar">
      <div class="brand-lockup" aria-label="HearthGhost">
        <span class="brand-mark" aria-hidden="true"></span>
        <span class="brand-name">HearthGhost · Windows</span>
      </div>
      <button class="quiet-button" type="button" data-connect>Connect</button>
    </header>

    <section class="character-stage windows-character-stage" aria-label="HearthGhost character and response">
      <div class="character-identity" aria-live="polite">
        <span class="character-identity-label">Character</span>
        <strong data-character-name>HearthGhost</strong>
      </div>
      <section class="character-viewport" aria-label="HearthGhost character viewport"></section>
      <div class="response-layer">
        <output class="response" data-response aria-live="polite"></output>
      </div>
    </section>

    <section class="interaction-panel windows-interaction-panel">
      <p class="notice" data-notice>Windows native mTLS transport is disconnected.</p>
      <div class="windows-node-status" data-node-status>Node: disconnected</div>
      <div class="character-selector" aria-label="Character selection">
        ${CHARACTER_CATALOG.map((entry) => `
          <button type="button" class="chip" data-character-id="${entry.id}">
            ${entry.name} · ${entry.sample.replace("AvatarSample_", "Avatar ")}
          </button>
        `).join("")}
      </div>
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
const viewport = new CharacterViewport(viewportElement, await loadCharacterRenderer("dom"));
await viewport.mount();
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
let renderedCharacterId: string | null = null;
let profileApplySequence = 0;

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
}

async function applyCharacterProfile(profile: CharacterDisplayProfile | null): Promise<void> {
  if (profile === null) {
    return;
  }
  characterName.textContent = profile.name;
  viewportElement.setAttribute("aria-label", `${profile.name} character viewport`);
  const selected = characterByName(profile.name);
  if (selected === null || selected.id === renderedCharacterId) {
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

async function submitText(text: string): Promise<void> {
  const normalized = text.trim();
  if (normalized === "") {
    return;
  }
  await ensureConversationOpen();
  character.beginThinking();
  const snapshot = await conversation.submit(normalized);
  await applyCharacterProfile(snapshot.characterProfile);
  const reply = snapshot.responseText ?? "";
  if (reply !== "") {
    historyView.render(history.append("user", normalized));
    historyView.render(history.append("assistant", reply));
    response.textContent = reply;
  }
  character.engage();
  notice.textContent = "Conversation active over Windows native mTLS.";
}

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
      character.acknowledgeSuccess();
      notice.textContent = "Windows Node connected with mTLS. Character and conversation testing are ready.";
      input.focus();
    } catch (error) {
      character.showConcern();
      showNodeSnapshot();
      notice.textContent = error instanceof Error ? error.message : "Windows Node connection failed";
    }
  })();
});

for (const button of root.querySelectorAll<HTMLButtonElement>("[data-character-id]")) {
  button.addEventListener("click", () => {
    void (async () => {
      const selected = CHARACTER_CATALOG.find((entry) => entry.id === button.dataset.characterId);
      if (selected === undefined) {
        return;
      }
      if (!node.canUseCapability("conversation.text")) {
        character.showConcern();
        notice.textContent = "Connect a trusted Windows Node before changing the character.";
        return;
      }
      try {
        await submitText(selectionCommand(selected));
      } catch (error) {
        character.showConcern();
        notice.textContent = error instanceof Error ? error.message : "Character selection failed";
      }
    })();
  });
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
