import type { CharacterRenderer } from "./renderer.js";
import type { CharacterPresentation } from "./semantic.js";

export class DomCharacterRenderer implements CharacterRenderer {
  private surface: HTMLDivElement | null = null;

  async mount(viewport: HTMLElement): Promise<void> {
    const surface = document.createElement("div");
    surface.className = "character-placeholder";
    surface.setAttribute("role", "img");
    surface.setAttribute("aria-label", "HearthGhost character");
    surface.textContent = "HG";
    viewport.replaceChildren(surface);
    this.surface = surface;
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
  }
}
