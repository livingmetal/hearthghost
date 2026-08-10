import type { CharacterRenderer } from "./renderer.js";
import {
  INITIAL_PRESENTATION,
  parseCharacterSemanticEvent,
  reduceCharacterPresentation,
  type CharacterPresentation,
} from "./semantic.js";

export class CharacterViewport {
  private presentation: CharacterPresentation = INITIAL_PRESENTATION;
  private resizeObserver: ResizeObserver | null = null;

  constructor(
    private readonly element: HTMLElement,
    private readonly renderer: CharacterRenderer,
  ) {}

  async mount(): Promise<void> {
    await this.renderer.mount(this.element);
    this.renderer.present(this.presentation);
    this.resize();
    if (typeof ResizeObserver !== "undefined") {
      this.resizeObserver = new ResizeObserver(() => this.resize());
      this.resizeObserver.observe(this.element);
    }
  }

  present(rawEvent: unknown): CharacterPresentation {
    const event = parseCharacterSemanticEvent(rawEvent);
    this.presentation = reduceCharacterPresentation(this.presentation, event);
    this.renderer.present(this.presentation);
    return this.presentation;
  }

  snapshot(): CharacterPresentation {
    return this.presentation;
  }

  suspend(): void {
    this.renderer.suspend();
  }

  resume(): void {
    this.resize();
    this.renderer.resume();
  }

  dispose(): void {
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
    this.renderer.dispose();
  }

  private resize(): void {
    const bounds = this.element.getBoundingClientRect();
    const pixelRatio = Math.min(globalThis.devicePixelRatio ?? 1, 2);
    this.renderer.resize(bounds.width, bounds.height, pixelRatio);
  }
}
