import {
  CHARACTER_CATALOG,
  characterById,
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

function optionLabel(entry: (typeof CHARACTER_CATALOG)[number]): string {
  return `${entry.name} · ${entry.sample.replace("AvatarSample_", "Avatar ")}`;
}

export function characterOptionsMarkup(
  selectedId: HearthGhostCharacterId,
): string {
  const options = CHARACTER_CATALOG.map((entry) => {
    const selected = entry.id === selectedId ? " selected" : "";
    return `<option value="${escapeAttribute(entry.id)}"${selected}>${optionLabel(entry)}</option>`;
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

export function synchronizeCharacterOptionsCatalog(root: ParentNode): boolean {
  const select = root.querySelector<HTMLSelectElement>("[data-character-select]");
  if (select === null) {
    return false;
  }
  const selected = characterById(select.value)?.id ?? null;
  const fragment = document.createDocumentFragment();
  for (const entry of CHARACTER_CATALOG) {
    const option = document.createElement("option");
    option.value = entry.id;
    option.textContent = optionLabel(entry);
    fragment.append(option);
  }
  select.replaceChildren(fragment);
  if (selected !== null) {
    select.value = selected;
  }
  select.dataset.catalogSource = "shared";
  return true;
}

if (typeof document !== "undefined" && typeof MutationObserver !== "undefined") {
  const synchronize = (): boolean => synchronizeCharacterOptionsCatalog(document);
  if (!synchronize()) {
    const observer = new MutationObserver(() => {
      if (synchronize()) {
        observer.disconnect();
      }
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }
}
