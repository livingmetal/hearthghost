import type { CharacterRenderer } from "./renderer.js";
import type { CharacterPresentation } from "./semantic.js";

const STATE_LABELS: Record<CharacterPresentation["state"], string> = {
  sleeping: "Sleeping",
  noticing: "Noticing",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
  engaged: "Here",
};

export class DomCharacterRenderer implements CharacterRenderer {
  private surface: HTMLDivElement | null = null;
  private stateLabel: HTMLSpanElement | null = null;

  async mount(viewport: HTMLElement): Promise<void> {
    const surface = document.createElement("div");
    surface.className = "character-avatar";
    surface.setAttribute("role", "img");
    surface.setAttribute("aria-label", "HearthGhost character sleeping");
    surface.innerHTML = `
      <div class="character-aura" aria-hidden="true"></div>
      <div class="character-head" aria-hidden="true">
        <span class="character-ear character-ear-left"></span>
        <span class="character-ear character-ear-right"></span>
        <span class="character-eye character-eye-left"></span>
        <span class="character-eye character-eye-right"></span>
        <span class="character-mouth"></span>
        <span class="character-cheek character-cheek-left"></span>
        <span class="character-cheek character-cheek-right"></span>
      </div>
      <span class="character-state-label"></span>
    `;
    viewport.replaceChildren(surface);
    this.surface = surface;
    this.stateLabel = surface.querySelector<HTMLSpanElement>(".character-state-label");
  }

  resize(_width: number, _height: number, _pixelRatio: number): void {}

  present(presentation: CharacterPresentation): void {
    if (this.surface === null) {
      return;
    }
    this.surface.dataset.state = presentation.state;
    this.surface.dataset.emotion = presentation.emotion;
    this.surface.setAttribute(
      "aria-label",
      `HearthGhost is ${presentation.state} and ${presentation.emotion}`,
    );
    if (this.stateLabel !== null) {
      this.stateLabel.textContent = STATE_LABELS[presentation.state];
    }
  }

  suspend(): void {
    this.surface?.setAttribute("data-suspended", "true");
  }

  resume(): void {
    this.surface?.removeAttribute("data-suspended");
  }

  dispose(): void {
    this.surface?.remove();
    this.surface = null;
    this.stateLabel = null;
  }
}
