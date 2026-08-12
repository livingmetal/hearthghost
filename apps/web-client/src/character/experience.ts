import { exitPreludeGestureFor } from "./presence-performance.js";
import type {
  CharacterEmotion,
  CharacterGesture,
  CharacterPresence,
  CharacterState,
} from "./semantic.js";
import type { CharacterViewport } from "./viewport.js";

export type CharacterPresenceScheduler = (
  callback: () => void,
  delayMillis: number,
) => void;

const ENTER_DURATION_MILLIS = 850;
const EXIT_DURATION_MILLIS = 650;

const scheduleWithPlatformTimer: CharacterPresenceScheduler = (callback, delayMillis) => {
  globalThis.setTimeout(callback, delayMillis);
};

export class CharacterExperienceController {
  private presenceSequence = 0;
  private exitPreludeCycle = 0;

  constructor(
    private readonly viewport: CharacterViewport,
    private readonly schedule: CharacterPresenceScheduler = scheduleWithPlatformTimer,
  ) {}

  presentServerEvent(event: unknown): void {
    this.viewport.present(event);
  }

  performGesture(gesture: CharacterGesture): void {
    this.viewport.present({ type: "character.gesture", payload: gesture });
  }

  performGestures(gestures: readonly CharacterGesture[]): void {
    for (const gesture of gestures) {
      this.performGesture(gesture);
    }
  }

  express(emotion: CharacterEmotion): void {
    this.setEmotion(emotion);
  }

  wakeByTouch(): void {
    this.enterStage();
    this.setEmotion("curious");
    this.setState("noticing");
  }

  beginListening(): void {
    this.ensurePresentOrEntering();
    this.setEmotion("curious");
    this.setState("listening");
  }

  beginThinking(): void {
    this.ensurePresentOrEntering();
    this.setEmotion("neutral");
    this.setState("thinking");
  }

  beginSpeaking(): void {
    this.ensurePresentOrEntering();
    this.setState("speaking");
  }

  engage(): void {
    this.setState("engaged");
  }

  acknowledgeSuccess(): void {
    this.setEmotion("happy");
    this.setState("engaged");
  }

  showConcern(): void {
    this.setEmotion("concerned");
    if (this.viewport.snapshot().state === "sleeping") {
      return;
    }
    this.setState("engaged");
  }

  sleep(): void {
    this.setEmotion("neutral");
    this.setState("sleeping");
    const prelude = exitPreludeGestureFor(this.viewport.characterId(), this.exitPreludeCycle++);
    if (prelude !== null) {
      this.performGesture(prelude);
    }
    this.exitStage();
  }

  private ensurePresentOrEntering(): void {
    if (this.viewport.snapshot().presence === "offstage") {
      this.enterStage();
    }
  }

  private enterStage(): void {
    const presence = this.viewport.snapshot().presence;
    const sequence = ++this.presenceSequence;
    if (presence === "present" || presence === "entering") {
      return;
    }
    this.setPresence("entering");
    this.schedule(() => {
      if (sequence === this.presenceSequence) {
        this.setPresence("present");
      }
    }, ENTER_DURATION_MILLIS);
  }

  private exitStage(): void {
    const presence = this.viewport.snapshot().presence;
    if (presence === "offstage") {
      return;
    }
    const sequence = ++this.presenceSequence;
    this.setPresence("exiting");
    this.schedule(() => {
      if (sequence === this.presenceSequence) {
        this.setPresence("offstage");
      }
    }, EXIT_DURATION_MILLIS);
  }

  private setState(state: CharacterState): void {
    this.viewport.present({ type: "character.state", payload: { state } });
  }

  private setEmotion(emotion: CharacterEmotion): void {
    this.viewport.present({ type: "character.emotion", payload: { emotion } });
  }

  private setPresence(presence: CharacterPresence): void {
    this.viewport.present({ type: "character.presence", payload: { presence } });
  }
}
