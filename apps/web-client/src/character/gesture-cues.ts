import { publishCharacterGesture } from "./gesture-bus.js";
import type { CharacterGesture } from "./semantic.js";

const NEGATION_PATTERN = /(?:하지\s*마|지\s*마|지\s*말(?:고|아|자)?|말고|말아|안\s*(?:해|해줘|하)|don't|do not)/iu;
const WAVE_VERB = "(?:흔들|흔든|흔들어|흔들고|wave)";
const RECENT_USER_GESTURE_MILLIS = 5_000;

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
  private observer: MutationObserver | null = null;
  private responseHost: HTMLElement | null = null;
  private readonly assistantSeen = new Set<string>();
  private readonly recentUser = new Map<string, number>();

  install(): void {
    document.addEventListener("submit", this.onSubmit, true);
    this.tryAttachResponse();
    this.observer = new MutationObserver(() => {
      this.tryAttachResponse();
      this.processResponse();
    });
    this.observer.observe(document.documentElement, {
      childList: true,
      characterData: true,
      subtree: true,
    });
  }

  dispose(): void {
    document.removeEventListener("submit", this.onSubmit, true);
    this.observer?.disconnect();
    this.observer = null;
    this.responseHost = null;
    this.assistantSeen.clear();
    this.recentUser.clear();
  }

  private tryAttachResponse(): void {
    if (this.responseHost !== null && this.responseHost.isConnected) {
      return;
    }
    this.responseHost = document.querySelector<HTMLElement>("[data-response]");
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
    const now = Date.now();
    for (const gesture of inferCharacterGestures(input.value)) {
      const key = gestureKey(gesture);
      this.recentUser.set(key, now);
      publishCharacterGesture(gesture);
    }
    for (const [key, timestamp] of this.recentUser) {
      if (now - timestamp > RECENT_USER_GESTURE_MILLIS) {
        this.recentUser.delete(key);
      }
    }
  };

  private processResponse(): void {
    const text = this.responseHost?.textContent?.trim() ?? "";
    if (text === "") {
      return;
    }
    const now = Date.now();
    for (const gesture of inferCharacterGestures(text)) {
      const key = gestureKey(gesture);
      if (this.assistantSeen.has(key)) {
        continue;
      }
      this.assistantSeen.add(key);
      const userTimestamp = this.recentUser.get(key);
      if (userTimestamp !== undefined && now - userTimestamp <= RECENT_USER_GESTURE_MILLIS) {
        continue;
      }
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
