import { subscribeCharacterGestures } from "./gesture-bus.js";
import type { CharacterRenderer } from "./renderer.js";
import {
  INITIAL_PRESENTATION,
  parseCharacterSemanticEvent,
  reduceCharacterPresentation,
  type CharacterPresentation,
  type CharacterPresence,
} from "./semantic.js";

interface PresenceMotionProfile {
  readonly entryX: string;
  readonly entryY: string;
  readonly exitX: string;
  readonly exitY: string;
  readonly scale: number;
  readonly durationMillis: number;
}

const YOUNGHEE_PRESENCE: PresenceMotionProfile = Object.freeze({
  entryX: "-44%",
  entryY: "7%",
  exitX: "-50%",
  exitY: "8%",
  scale: 0.975,
  durationMillis: 900,
});

const CHEOLSU_PRESENCE: PresenceMotionProfile = Object.freeze({
  entryX: "38%",
  entryY: "3%",
  exitX: "44%",
  exitY: "4%",
  scale: 0.99,
  durationMillis: 760,
});

const GENERIC_PRESENCE: PresenceMotionProfile = Object.freeze({
  entryX: "-42%",
  entryY: "5%",
  exitX: "-46%",
  exitY: "7%",
  scale: 0.985,
  durationMillis: 850,
});

export class CharacterViewport {
  private presentation: CharacterPresentation = INITIAL_PRESENTATION;
  private resizeObserver: ResizeObserver | null = null;
  private unsubscribeGestures: (() => void) | null = null;

  constructor(
    private readonly element: HTMLElement,
    private renderer: CharacterRenderer,
  ) {}

  async mount(): Promise<void> {
    this.applyPresenceMetadata();
    await this.renderer.mount(this.element);
    this.applyPresentation();
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
      this.applyPresenceToSurface();
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
    this.applyPresentation();
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

  private applyPresentation(): void {
    this.renderer.present(this.presentation);
    this.applyPresenceMetadata();
    this.applyPresenceToSurface();
  }

  private applyPresenceMetadata(): void {
    this.element.dataset.characterPresence = this.presentation.presence;
    this.element.dataset.characterState = this.presentation.state;
    this.element.style.overflow = "hidden";
    if (this.presentation.presence === "offstage") {
      this.element.setAttribute("aria-hidden", "true");
    } else {
      this.element.removeAttribute("aria-hidden");
    }
  }

  private applyPresenceToSurface(): void {
    const surface = this.element.firstElementChild;
    if (!(surface instanceof HTMLElement)) {
      return;
    }
    const profile = this.presenceProfile();
    const reducedMotion = globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
    const duration = reducedMotion ? 1 : profile.durationMillis;
    surface.style.transformOrigin = "50% 70%";
    surface.style.willChange = "transform, opacity";
    surface.style.transition = [
      `transform ${duration}ms cubic-bezier(0.22, 0.72, 0.22, 1)`,
      `opacity ${Math.max(1, Math.round(duration * 0.72))}ms ease`,
    ].join(", ");

    const style = this.presenceStyle(this.presentation.presence, profile);
    surface.style.opacity = style.opacity;
    surface.style.pointerEvents = style.pointerEvents;
    surface.style.transform = style.transform;
  }

  private presenceProfile(): PresenceMotionProfile {
    const label = this.element.getAttribute("aria-label") ?? "";
    if (label.startsWith("영희")) {
      return YOUNGHEE_PRESENCE;
    }
    if (label.startsWith("철수")) {
      return CHEOLSU_PRESENCE;
    }
    return GENERIC_PRESENCE;
  }

  private presenceStyle(
    presence: CharacterPresence,
    profile: PresenceMotionProfile,
  ): Readonly<{ opacity: string; pointerEvents: string; transform: string }> {
    if (presence === "entering" || presence === "present") {
      return Object.freeze({
        opacity: "1",
        pointerEvents: "auto",
        transform: "translate3d(0, 0, 0) scale(1)",
      });
    }
    const exiting = presence === "exiting";
    const x = exiting ? profile.exitX : profile.entryX;
    const y = exiting ? profile.exitY : profile.entryY;
    return Object.freeze({
      opacity: "0",
      pointerEvents: "none",
      transform: `translate3d(${x}, ${y}, 0) scale(${profile.scale})`,
    });
  }

  private resize(): void {
    const bounds = this.element.getBoundingClientRect();
    const pixelRatio = Math.min(globalThis.devicePixelRatio ?? 1, 2);
    this.renderer.resize(bounds.width, bounds.height, pixelRatio);
  }
}
