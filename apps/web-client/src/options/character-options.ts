import {
  CHARACTER_CATALOG,
  characterById,
  type HearthGhostCharacterId,
} from "../character/catalog.js";
import type {
  PersonaFormality,
  PersonaHumor,
  PersonaInitiative,
  PersonaProfilePreset,
  PersonaVerbosity,
} from "./persona-profiles.js";

export interface CharacterOptionsElements {
  readonly details: HTMLDetailsElement;
  readonly appearanceSelect: HTMLSelectElement;
  readonly appearanceStatus: HTMLElement;
  readonly personaSelect: HTMLSelectElement;
  readonly personaName: HTMLInputElement;
  readonly personaHumor: HTMLSelectElement;
  readonly personaVerbosity: HTMLSelectElement;
  readonly personaFormality: HTMLSelectElement;
  readonly personaInitiative: HTMLSelectElement;
  readonly personaNew: HTMLButtonElement;
  readonly personaSave: HTMLButtonElement;
  readonly personaDelete: HTMLButtonElement;
  readonly personaStatus: HTMLElement;
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
  profiles: readonly PersonaProfilePreset[],
  selectedPersonaId: string,
): string {
  const appearanceOptions = CHARACTER_CATALOG.map((entry) => {
    const selected = entry.id === selectedId ? " selected" : "";
    return `<option value="${escapeAttribute(entry.id)}"${selected}>${optionLabel(entry)}</option>`;
  }).join("");
  const personaOptions = profiles.map((profile) => {
    const selected = profile.id === selectedPersonaId ? " selected" : "";
    const suffix = profile.builtIn ? " · built-in" : " · custom";
    return `<option value="${escapeAttribute(profile.id)}"${selected}>${escapeAttribute(profile.name + suffix)}</option>`;
  }).join("");
  const persona = profiles.find((profile) => profile.id === selectedPersonaId) ?? profiles[0];
  if (persona === undefined) {
    throw new Error("At least one persona profile is required");
  }

  return `
    <details class="app-options" data-options>
      <summary>Options</summary>
      <div class="options-panel" aria-label="HearthGhost options">
        <section class="option-section" aria-labelledby="appearance-options-title">
          <h2 id="appearance-options-title">Appearance</h2>
          <label for="character-option">VRM model and local voice</label>
          <select id="character-option" class="character-select" data-character-select aria-label="Character appearance">
            ${appearanceOptions}
          </select>
          <p class="character-setting-status" data-character-setting-status>Saved on this device.</p>
        </section>
        <section class="option-section" aria-labelledby="persona-options-title">
          <h2 id="persona-options-title">Persona</h2>
          <label for="persona-option">Profile</label>
          <select id="persona-option" class="character-select" data-persona-select aria-label="Persona profile">
            ${personaOptions}
          </select>
          <label for="persona-name">Name</label>
          <input id="persona-name" class="persona-name-input" data-persona-name maxlength="80" value="${escapeAttribute(persona.name)}" />
          <div class="persona-field-grid">
            ${personaSelectMarkup("Humor", "humor", ["low", "moderate", "high"], persona.humor)}
            ${personaSelectMarkup("Response length", "verbosity", ["concise", "normal", "detailed"], persona.verbosity)}
            ${personaSelectMarkup("Formality", "formality", ["casual", "neutral", "formal"], persona.formality)}
            ${personaSelectMarkup("Initiative", "initiative", ["low", "moderate", "high"], persona.initiative)}
          </div>
          <div class="persona-actions">
            <button type="button" data-persona-new>New</button>
            <button type="button" data-persona-save>Save & apply</button>
            <button type="button" data-persona-delete>Delete</button>
          </div>
          <p class="character-setting-status" data-persona-setting-status>
            Core stores the active persona; this device only caches editing presets.
          </p>
        </section>
      </div>
    </details>
  `;
}

function personaSelectMarkup(
  label: string,
  field: string,
  values: readonly string[],
  selectedValue: string,
): string {
  const options = values.map((value) =>
    `<option value="${value}"${value === selectedValue ? " selected" : ""}>${value}</option>`
  ).join("");
  return `<label>${label}<select data-persona-${field}>${options}</select></label>`;
}

export function requireCharacterOptions(root: ParentNode): CharacterOptionsElements {
  const elements = {
    details: root.querySelector<HTMLDetailsElement>("[data-options]"),
    appearanceSelect: root.querySelector<HTMLSelectElement>("[data-character-select]"),
    appearanceStatus: root.querySelector<HTMLElement>("[data-character-setting-status]"),
    personaSelect: root.querySelector<HTMLSelectElement>("[data-persona-select]"),
    personaName: root.querySelector<HTMLInputElement>("[data-persona-name]"),
    personaHumor: root.querySelector<HTMLSelectElement>("[data-persona-humor]"),
    personaVerbosity: root.querySelector<HTMLSelectElement>("[data-persona-verbosity]"),
    personaFormality: root.querySelector<HTMLSelectElement>("[data-persona-formality]"),
    personaInitiative: root.querySelector<HTMLSelectElement>("[data-persona-initiative]"),
    personaNew: root.querySelector<HTMLButtonElement>("[data-persona-new]"),
    personaSave: root.querySelector<HTMLButtonElement>("[data-persona-save]"),
    personaDelete: root.querySelector<HTMLButtonElement>("[data-persona-delete]"),
    personaStatus: root.querySelector<HTMLElement>("[data-persona-setting-status]"),
  };
  if (Object.values(elements).some((element) => element === null)) {
    throw new Error("Shared character options are missing");
  }
  return elements as CharacterOptionsElements;
}

export function setCharacterOptionsStatus(elements: CharacterOptionsElements, message: string): void {
  elements.appearanceStatus.textContent = message;
}

export function setPersonaOptionsStatus(elements: CharacterOptionsElements, message: string): void {
  elements.personaStatus.textContent = message;
}

export function selectCharacterOption(elements: CharacterOptionsElements, id: HearthGhostCharacterId): void {
  elements.appearanceSelect.value = id;
}

export function populatePersonaOptions(
  elements: CharacterOptionsElements,
  profiles: readonly PersonaProfilePreset[],
  selectedId: string,
): void {
  const fragment = document.createDocumentFragment();
  for (const profile of profiles) {
    const option = document.createElement("option");
    option.value = profile.id;
    option.textContent = `${profile.name} · ${profile.builtIn ? "built-in" : "custom"}`;
    fragment.append(option);
  }
  elements.personaSelect.replaceChildren(fragment);
  elements.personaSelect.value = selectedId;
}

export function writePersonaForm(elements: CharacterOptionsElements, profile: PersonaProfilePreset): void {
  elements.personaSelect.value = profile.id;
  elements.personaName.value = profile.name;
  elements.personaHumor.value = profile.humor;
  elements.personaVerbosity.value = profile.verbosity;
  elements.personaFormality.value = profile.formality;
  elements.personaInitiative.value = profile.initiative;
  elements.personaDelete.disabled = profile.builtIn;
}

export function readPersonaForm(
  elements: CharacterOptionsElements,
): Omit<PersonaProfilePreset, "id" | "builtIn"> {
  return {
    name: elements.personaName.value.trim(),
    humor: elements.personaHumor.value as PersonaHumor,
    verbosity: elements.personaVerbosity.value as PersonaVerbosity,
    formality: elements.personaFormality.value as PersonaFormality,
    initiative: elements.personaInitiative.value as PersonaInitiative,
  };
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
