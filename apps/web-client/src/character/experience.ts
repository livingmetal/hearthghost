import type {
  CharacterEmotion,
  CharacterGesture,
  CharacterState,
} from "./semantic.js";
import type { CharacterViewport } from "./viewport.js";

export class CharacterExperienceController {
  constructor(private readonly viewport: CharacterViewport) {}

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

  wakeByTouch(): void {
    this.setEmotion("curious");
    this.setState("noticing");
  }

  beginListening(): void {
    this.setEmotion("curious");
    this.setState("listening");
  }

  beginThinking(): void {
    this.setEmotion("neutral");
    this.setState("thinking");
  }

  beginSpeaking(): void {
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
  }

  private setState(state: CharacterState): void {
    this.viewport.present({ type: "character.state", payload: { state } });
  }

  private setEmotion(emotion: CharacterEmotion): void {
    this.viewport.present({ type: "character.emotion", payload: { emotion } });
  }
}
