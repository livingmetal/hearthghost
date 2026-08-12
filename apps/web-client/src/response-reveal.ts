import {
  RESPONSE_REVEAL_DONE_EVENT,
  RESPONSE_REVEAL_START_EVENT,
  type ResponseRevealDetail,
} from "./character/performance-events.js";
import {
  SPEECH_DONE_EVENT,
  SPEECH_ERROR_EVENT,
  SPEECH_RANGE_EVENT,
  SPEECH_START_EVENT,
  type SpeechPresentationDetail,
  type SpeechRangePresentationDetail,
} from "./voice/speech-presentation.js";

export { RESPONSE_REVEAL_DONE_EVENT, RESPONSE_REVEAL_START_EVENT };
export type { ResponseRevealDetail };

const FALLBACK_STEP_MILLIS = 90;
const FALLBACK_START_DELAY_MILLIS = 120;

function sameSpeechText(left: string, right: string): boolean {
  return left.trim() === right.trim();
}

function graphemeOffsets(text: string): readonly number[] {
  const offsets: number[] = [];
  let offset = 0;
  for (const grapheme of Array.from(text)) {
    offset += grapheme.length;
    offsets.push(offset);
  }
  return offsets;
}

export class ResponseRevealController {
  private host: HTMLOutputElement | null = null;
  private hostObserver: MutationObserver | null = null;
  private rootObserver: MutationObserver | null = null;
  private fullText = "";
  private offsets: readonly number[] = [];
  private fallbackIndex = 0;
  private fallbackTimer: number | null = null;
  private activeUtteranceId: string | null = null;
  private hasSpeechRange = false;

  install(): void {
    this.tryAttach();
    if (this.host !== null) {
      return;
    }
    this.rootObserver = new MutationObserver(() => this.tryAttach());
    this.rootObserver.observe(document.documentElement, { childList: true, subtree: true });
  }

  dispose(): void {
    this.stopFallback();
    this.hostObserver?.disconnect();
    this.rootObserver?.disconnect();
    this.hostObserver = null;
    this.rootObserver = null;
    window.removeEventListener(SPEECH_START_EVENT, this.onSpeechStart as EventListener);
    window.removeEventListener(SPEECH_RANGE_EVENT, this.onSpeechRange as EventListener);
    window.removeEventListener(SPEECH_DONE_EVENT, this.onSpeechDone as EventListener);
    window.removeEventListener(SPEECH_ERROR_EVENT, this.onSpeechError as EventListener);
  }

  private tryAttach(): void {
    if (this.host !== null) {
      return;
    }
    const candidate = document.querySelector<HTMLOutputElement>("[data-response]");
    if (candidate === null) {
      return;
    }
    this.host = candidate;
    this.rootObserver?.disconnect();
    this.rootObserver = null;
    this.hostObserver = new MutationObserver(() => this.captureExternalText());
    this.observeHost();
    window.addEventListener(SPEECH_START_EVENT, this.onSpeechStart as EventListener);
    window.addEventListener(SPEECH_RANGE_EVENT, this.onSpeechRange as EventListener);
    window.addEventListener(SPEECH_DONE_EVENT, this.onSpeechDone as EventListener);
    window.addEventListener(SPEECH_ERROR_EVENT, this.onSpeechError as EventListener);
  }

  private observeHost(): void {
    this.hostObserver?.observe(this.host!, { childList: true, characterData: true, subtree: true });
  }

  private captureExternalText(): void {
    const text = this.host?.textContent ?? "";
    if (text === "") {
      this.stopFallback();
      this.fullText = "";
      this.offsets = [];
      this.fallbackIndex = 0;
      this.activeUtteranceId = null;
      this.hasSpeechRange = false;
      this.host?.setAttribute("aria-busy", "false");
      return;
    }
    this.beginReveal(text);
  }

  private beginReveal(text: string): void {
    this.stopFallback();
    this.activeUtteranceId = null;
    this.hasSpeechRange = false;
    this.fullText = text.trim();
    this.offsets = graphemeOffsets(this.fullText);
    this.fallbackIndex = 0;
    this.host?.setAttribute("aria-busy", "true");
    window.dispatchEvent(new CustomEvent<ResponseRevealDetail>(RESPONSE_REVEAL_START_EVENT, {
      detail: { text: this.fullText },
    }));
    this.write("");
    this.fallbackTimer = window.setTimeout(() => this.fallbackStep(), FALLBACK_START_DELAY_MILLIS);
  }

  private fallbackStep(): void {
    this.fallbackTimer = null;
    if (this.fullText === "" || this.hasSpeechRange) {
      return;
    }
    const end = this.offsets[this.fallbackIndex];
    if (end === undefined) {
      this.finishReveal();
      return;
    }
    this.fallbackIndex += 1;
    this.write(this.fullText.slice(0, end));
    const grapheme = this.fullText.slice(this.offsets[this.fallbackIndex - 2] ?? 0, end);
    const punctuationPause = /[.!?。！？]/u.test(grapheme)
      ? 260
      : /[,，;:]/u.test(grapheme)
        ? 120
        : 0;
    this.fallbackTimer = window.setTimeout(
      () => this.fallbackStep(),
      FALLBACK_STEP_MILLIS + punctuationPause,
    );
  }

  private readonly onSpeechStart = (event: CustomEvent<SpeechPresentationDetail>): void => {
    if (!sameSpeechText(this.fullText, event.detail.text)) {
      return;
    }
    this.stopFallback();
    this.activeUtteranceId = event.detail.utteranceId;
    this.hasSpeechRange = false;
    this.fallbackTimer = window.setTimeout(() => this.fallbackStep(), 240);
  };

  private readonly onSpeechRange = (event: CustomEvent<SpeechRangePresentationDetail>): void => {
    if (
      this.activeUtteranceId !== event.detail.utteranceId
      || !sameSpeechText(this.fullText, event.detail.text)
    ) {
      return;
    }
    this.hasSpeechRange = true;
    this.stopFallback();
    this.write(this.fullText.slice(0, Math.min(event.detail.end, this.fullText.length)));
  };

  private readonly onSpeechDone = (event: CustomEvent<SpeechPresentationDetail>): void => {
    if (
      this.activeUtteranceId !== event.detail.utteranceId
      || !sameSpeechText(this.fullText, event.detail.text)
    ) {
      return;
    }
    this.finishReveal();
  };

  private readonly onSpeechError = (event: CustomEvent<SpeechPresentationDetail>): void => {
    if (
      !sameSpeechText(this.fullText, event.detail.text)
      || (this.activeUtteranceId !== null && this.activeUtteranceId !== event.detail.utteranceId)
    ) {
      return;
    }
    this.finishReveal();
  };

  private finishReveal(): void {
    const completedText = this.fullText;
    this.activeUtteranceId = null;
    this.hasSpeechRange = false;
    this.stopFallback();
    this.write(completedText);
    this.host?.setAttribute("aria-busy", "false");
    if (completedText !== "") {
      window.dispatchEvent(new CustomEvent<ResponseRevealDetail>(RESPONSE_REVEAL_DONE_EVENT, {
        detail: { text: completedText },
      }));
    }
  }

  private stopFallback(): void {
    if (this.fallbackTimer !== null) {
      window.clearTimeout(this.fallbackTimer);
      this.fallbackTimer = null;
    }
  }

  private write(text: string): void {
    if (this.host === null || this.hostObserver === null) {
      return;
    }
    this.hostObserver.disconnect();
    this.host.textContent = text;
    this.observeHost();
  }
}

const responseReveal = new ResponseRevealController();
responseReveal.install();
window.addEventListener("pagehide", () => responseReveal.dispose(), { once: true });
