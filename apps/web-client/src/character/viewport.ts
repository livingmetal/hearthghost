import { subscribeCharacterGestures } from "./gesture-bus.js";
import {
  characterIdFromViewportLabel,
  presenceMotionFor,
} from "./presence-performance.js";
import type { CharacterRenderer } from "./renderer.js";
import {
  INITIAL_PRESENTATION,
  parseCharacterSemanticEvent,
  reduceCharacterPresentation,
  type CharacterPresentation,
  type CharacterPresence,
} from "./semantic.js";

export class CharacterViewport {
  private presentation: CharacterPresentation = INITIAL_PRESENTATION;
  private resizeObserver: ResizeObserver | null = null;
  private unsubscribeGestures: (() => void) | null = null;
  private renderedPresence: CharacterPresence | null = null;
  private presenceAnimation: Animation | null = null;
  private entranceCycle = 0;
  private exitCycle = 0;

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
      this.presenceAnimation?.cancel();
      this.presenceAnimation = null;
      this.renderedPresence = null;
      this.applyPresenceToSurface();
      if (this.presentation.presence === "offstage") {
        renderer.suspend();
      }
      this.renderer = renderer;
      this.resize();
      prior.dispose();
    } catch (error) {
      renderer.dispose();
      if (this.presentation.presence !== "offstage") {
        prior.resume();
      }
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

  characterId(): "younghee" | "cheolsu" | null {
    return characterIdFromViewportLabel(this.element.getAttribute("aria-label") ?? "");
  }

  suspend(): void {
    this.renderer.suspend();
  }

  resume(): void {
    this.resize();
    if (this.presentation.presence !== "offstage") {
      this.renderer.resume();
    }
  }

  dispose(): void {
    this.unsubscribeGestures?.();
    this.unsubscribeGestures = null;
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
    this.presenceAnimation?.cancel();
    this.presenceAnimation = null;
    this.renderer.dispose();
  }

  private applyPresentation(): void {
    this.renderer.present(this.presentation);
    this.applyPresenceMetadata();
    this.applyPresenceToSurface();
    if (this.presentation.presence === "offstage") {
      this.renderer.suspend();
    } else {
      this.renderer.resume();
    }
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
    if (typeof HTMLElement === "undefined" || !(surface instanceof HTMLElement)) {
      return;
    }

    const presence = this.presentation.presence;
    if (presence === this.renderedPresence) {
      return;
    }
    this.renderedPresence = presence;
    this.presenceAnimation?.cancel();
    this.presenceAnimation = null;

    const characterId = this.characterId();
    const reducedMotion = globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
    surface.style.transformOrigin = "50% 70%";
    surface.style.willChange = "transform, opacity";
    surface.style.pointerEvents = presence === "entering" || presence === "present" ? "auto" : "none";

    if ((presence === "entering" || presence === "exiting") && !reducedMotion && typeof surface.animate === "function") {
      const phase = presence === "entering" ? "enter" : "exit";
      const cycle = phase === "enter" ? this.entranceCycle++ : this.exitCycle++;
      const motion = presenceMotionFor(characterId, phase, cycle);
      const finalFrame = motion.keyframes.at(-1);
      if (finalFrame !== undefined) {
        surface.style.opacity = String(finalFrame.opacity);
        surface.style.transform = finalFrame.transform;
      }
      surface.style.transition = "none";
      const animation = surface.animate(
        motion.keyframes.map((frame) => ({
          opacity: frame.opacity,
          transform: frame.transform,
          offset: frame.offset,
        })),
        {
          duration: motion.durationMillis,
          easing: motion.easing,
          fill: "both",
        },
      );
      this.presenceAnimation = animation;
      animation.onfinish = () => {
        if (this.presenceAnimation === animation) {
          this.presenceAnimation = null;
          animation.cancel();
        }
      };
      return;
    }

    const fallback = presenceMotionFor(
      characterId,
      presence === "exiting" ? "exit" : "enter",
      0,
    );
    const duration = reducedMotion ? 1 : fallback.durationMillis;
    surface.style.transition = [
      `transform ${duration}ms cubic-bezier(0.22, 0.72, 0.22, 1)`,
      `opacity ${Math.max(1, Math.round(duration * 0.72))}ms ease`,
    ].join(", ");

    if (presence === "entering" || presence === "present") {
      surface.style.opacity = "1";
      surface.style.transform = "translate3d(0, 0, 0) scale(1)";
      return;
    }

    const frame = presence === "exiting"
      ? fallback.keyframes.at(-1)
      : presenceMotionFor(characterId, "enter", 0).keyframes[0];
    surface.style.opacity = String(frame?.opacity ?? 0);
    surface.style.transform = frame?.transform ?? "translate3d(-42%, 5%, 0) scale(0.985)";
  }

  private resize(): void {
    const bounds = this.element.getBoundingClientRect();
    const pixelRatio = Math.min(globalThis.devicePixelRatio ?? 1, 2);
    this.renderer.resize(bounds.width, bounds.height, pixelRatio);
  }
}
