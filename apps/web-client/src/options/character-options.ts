import {
  CHARACTER_CATALOG,
  type HearthGhostCharacterId,
} from "../character/catalog.js";

export interface CharacterOptionsElements {
  readonly details: HTMLDetailsElement;
  readonly select: HTMLSelectElement;
  readonly status: HTMLElement;
}

function escapeAttribute(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

export function characterOptionsMarkup(
  selectedId: HearthGhostCharacterId,
): string {
  const options = CHARACTER_CATALOG.map((entry) => {
    const selected = entry.id === selectedId ? " selected" : "";
    const sample = entry.sample.replace("AvatarSample_", "Avatar ");
    return `<option value="${escapeAttribute(entry.id)}"${selected}>${entry.name} · ${sample}</option>`;
  }).join("");

  return `
    <details class="app-options" data-options>
      <summary>Options</summary>
      <div class="options-panel" aria-label="HearthGhost options">
        <label for="character-option">Character</label>
        <select id="character-option" class="character-select" data-character-select aria-label="Character profile">
          ${options}
        </select>
        <p class="character-setting-status" data-character-setting-status>
          Saved on this device. Core persona syncs when a trusted conversation is available.
        </p>
      </div>
    </details>
  `;
}

export function requireCharacterOptions(
  root: ParentNode,
): CharacterOptionsElements {
  const details = root.querySelector<HTMLDetailsElement>("[data-options]");
  const select = root.querySelector<HTMLSelectElement>("[data-character-select]");
  const status = root.querySelector<HTMLElement>("[data-character-setting-status]");
  if (details === null || select === null || status === null) {
    throw new Error("Shared character options are missing");
  }
  return { details, select, status };
}

export function setCharacterOptionsStatus(
  elements: CharacterOptionsElements,
  message: string,
): void {
  elements.status.textContent = message;
}

export function selectCharacterOption(
  elements: CharacterOptionsElements,
  id: HearthGhostCharacterId,
): void {
  elements.select.value = id;
}
