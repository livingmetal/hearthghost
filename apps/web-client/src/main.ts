import "./styles.css";
import { BrowserDevelopmentNodePlatform } from "./node/browser-platform.js";
import { ClientNode } from "./node/client-node.js";
import { loadCharacterRenderer } from "./character/renderer-loader.js";
import { CharacterViewport } from "./character/viewport.js";

const root = document.querySelector<HTMLDivElement>("#app");
if (root === null) {
  throw new Error("HearthGhost client root is missing");
}

const node = new ClientNode(new BrowserDevelopmentNodePlatform());

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
      <div class="text-row">
        <input id="message" autocomplete="off" placeholder="Type to talk" />
        <button type="button" data-connect>Connect securely</button>
      </div>
      <p class="notice" data-notice>Text transport arrives in HG-009.</p>
    </section>
  </main>
`;

const connectButton = root.querySelector<HTMLButtonElement>("[data-connect]");
const nodeStatus = root.querySelector<HTMLElement>("[data-node-status]");
const notice = root.querySelector<HTMLElement>("[data-notice]");
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

connectButton?.addEventListener("click", async () => {
  const snapshot = await node.connect({
    kind: "platform-managed",
    reference: "not-provisioned",
  });
  if (nodeStatus !== null) {
    nodeStatus.textContent = `Node: ${snapshot.connection} / ${snapshot.trust}`;
  }
  if (notice !== null && snapshot.error !== null) {
    notice.textContent = snapshot.error;
  }
});

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") {
    void node.suspend();
    viewport.suspend();
  } else {
    viewport.resume();
  }
});
