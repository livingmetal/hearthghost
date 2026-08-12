import {
  RESPONSE_REVEAL_START_EVENT,
  type ResponseRevealDetail,
} from "./performance-events.js";
import { publishCharacterGesture } from "./gesture-bus.js";
import type { CharacterGesture } from "./semantic.js";

const NEGATION_PATTERN = /(?:하지\s*마|지\s*마|지\s*말(?:고|아|자)?|말고|말아|안\s*(?:해|해줘|하)|don't|do not)/iu;
const WAVE_VERB = "(?:흔들|흔든|흔들어|흔들고|wave)";

function gestureKey(gesture: CharacterGesture): string {
  if (gesture.gesture === "wave" || gesture.gesture === "raise_hand") {
    return `${gesture.gesture}:${gesture.side}`;
  }
  if (gesture.gesture === "turn") {
    return `${gesture.gesture}:${gesture.direction}`;
  }
  return gesture.gesture;
}

function appendUnique(target: CharacterGesture[], gesture: CharacterGesture): void {
  const key = gestureKey(gesture);
  if (!target.some((candidate) => gestureKey(candidate) === key)) {
    target.push(gesture);
  }
}

export function inferCharacterGestures(text: string): readonly CharacterGesture[] {
  const normalized = text.trim();
  if (normalized === "" || NEGATION_PATTERN.test(normalized)) {
    return [];
  }

  const gestures: CharacterGesture[] = [];

  if (/(?:왼손|왼팔|left\s+(?:hand|arm)).{0,16}(?:들|올리|raise|lift)/iu.test(normalized)) {
    appendUnique(gestures, { gesture: "raise_hand", side: "left" });
  }
  if (/(?:오른손|오른팔|right\s+(?:hand|arm)).{0,16}(?:들|올리|raise|lift)/iu.test(normalized)) {
    appendUnique(gestures, { gesture: "raise_hand", side: "right" });
  }

  const leftWave = new RegExp(`(?:왼손|왼팔|left\\s+(?:hand|arm)).{0,18}${WAVE_VERB}`, "iu");
  const rightWave = new RegExp(`(?:오른손|오른팔|right\\s+(?:hand|arm)).{0,18}${WAVE_VERB}`, "iu");
  const generalWave = new RegExp(
    `(?:손|hand).{0,18}${WAVE_VERB}|${WAVE_VERB}.{0,12}(?:손|hand)`,
    "iu",
  );

  if (leftWave.test(normalized)) {
    appendUnique(gestures, { gesture: "wave", side: "left" });
  }
  if (rightWave.test(normalized)) {
    appendUnique(gestures, { gesture: "wave", side: "right" });
  }
  if (
    !gestures.some((gesture) => gesture.gesture === "wave")
    && generalWave.test(normalized)
  ) {
    appendUnique(gestures, { gesture: "wave", side: "right" });
  }

  if (/(?:오른쪽|우측|right).{0,18}(?:한\s*바퀴|돌|회전|turn|spin)/iu.test(normalized)) {
    appendUnique(gestures, { gesture: "turn", direction: "right" });
  }
  if (/(?:왼쪽|좌측|left).{0,18}(?:한\s*바퀴|돌|회전|turn|spin)/iu.test(normalized)) {
    appendUnique(gestures, { gesture: "turn", direction: "left" });
  }

  if (/(?:고개.{0,10}끄덕|끄덕(?:여|인다|임|이고|이며)|\bnod\b)/iu.test(normalized)) {
    appendUnique(gestures, { gesture: "nod" });
  }
  if (/(?:고개.{0,10}(?:젓|저어|흔들|흔든)|도리도리|shake.{0,8}head)/iu.test(normalized)) {
    appendUnique(gestures, { gesture: "shake_head" });
  }
  if (/(?:허리|고개).{0,10}숙|(?:인사|절)(?:해|한다|하)|\bbow\b/iu.test(normalized)) {
    appendUnique(gestures, { gesture: "bow" });
  }

  return gestures;
}

export class GestureCueBridge {
  private readonly assistantSeen = new Set<string>();
  private readonly pendingUserGestures = new Map<string, CharacterGesture>();

  install(): void {
    document.addEventListener("submit", this.onSubmit, true);
    window.addEventListener(
      RESPONSE_REVEAL_START_EVENT,
      this.onResponseRevealStart as EventListener,
    );
  }

  dispose(): void {
    document.removeEventListener("submit", this.onSubmit, true);
    window.removeEventListener(
      RESPONSE_REVEAL_START_EVENT,
      this.onResponseRevealStart as EventListener,
    );
    this.assistantSeen.clear();
    this.pendingUserGestures.clear();
  }

  private readonly onSubmit = (event: SubmitEvent): void => {
    const form = event.target instanceof HTMLFormElement ? event.target : null;
    if (form === null || !form.matches("[data-conversation]")) {
      return;
    }
    const input = form.querySelector<HTMLInputElement | HTMLTextAreaElement>("#message");
    if (input === null) {
      return;
    }

    this.assistantSeen.clear();
    this.pendingUserGestures.clear();
    for (const gesture of inferCharacterGestures(input.value)) {
      this.pendingUserGestures.set(gestureKey(gesture), gesture);
    }
  };

  private readonly onResponseRevealStart = (
    event: CustomEvent<ResponseRevealDetail>,
  ): void => {
    this.processResponse(event.detail.text);
  };

  private processResponse(text: string): void {
    const normalized = text.trim();
    if (normalized === "") {
      return;
    }

    for (const [key, gesture] of this.pendingUserGestures) {
      if (!this.assistantSeen.has(key)) {
        this.assistantSeen.add(key);
        publishCharacterGesture(gesture);
      }
    }
    this.pendingUserGestures.clear();

    for (const gesture of inferCharacterGestures(normalized)) {
      const key = gestureKey(gesture);
      if (this.assistantSeen.has(key)) {
        continue;
      }
      this.assistantSeen.add(key);
      publishCharacterGesture(gesture);
    }
  }
}

if (typeof document !== "undefined" && typeof window !== "undefined") {
  const bridge = new GestureCueBridge();
  const install = (): void => bridge.install();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install, { once: true });
  } else {
    install();
  }
  window.addEventListener("pagehide", () => bridge.dispose(), { once: true });
}
