import { subscribeCharacterGestures } from "./gesture-bus.js";
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
  private unsubscribeGestures: (() => void) | null = null;

  constructor(
    private readonly element: HTMLElement,
    private renderer: CharacterRenderer,
  ) {}

  async mount(): Promise<void> {
    await this.renderer.mount(this.element);
    this.renderer.present(this.presentation);
    this.resize();
    if (typeof ResizeObserver !== "undefined") {
      this.resizeObserver = new ResizeObserver(() => this.resize());
      this.resizeObserver.observe(this.element);
    }
    this.unsubscribeGestures ??= subscribeCharacterGestures((gesture) => {
      this.present({ type: "character.gesture", payload: gesture });
    });
  }

  async replaceRenderer(renderer: CharacterRenderer): Promise<void> {
    const prior = this.renderer;
    prior.suspend();
    try {
      await renderer.mount(this.element);
      renderer.present(this.presentation);
      this.renderer = renderer;
      this.resize();
      prior.dispose();
    } catch (error) {
      renderer.dispose();
      prior.resume();
      throw error;
    }
  }

  present(rawEvent: unknown): CharacterPresentation {
    const event = parseCharacterSemanticEvent(rawEvent);
    if (event.type === "character.gesture") {
      this.renderer.performGesture?.(event.payload);
      return this.presentation;
    }
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
    this.unsubscribeGestures?.();
    this.unsubscribeGestures = null;
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
