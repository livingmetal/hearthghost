export const SPEECH_START_EVENT = "hearthghost:speech-start";
export const SPEECH_RANGE_EVENT = "hearthghost:speech-range";
export const SPEECH_DONE_EVENT = "hearthghost:speech-done";
export const SPEECH_ERROR_EVENT = "hearthghost:speech-error";

export interface SpeechPresentationDetail {
  readonly utteranceId: string;
  readonly text: string;
}

export interface SpeechRangePresentationDetail extends SpeechPresentationDetail {
  readonly start: number;
  readonly end: number;
}

export function dispatchSpeechStart(detail: SpeechPresentationDetail): void {
  window.dispatchEvent(new CustomEvent<SpeechPresentationDetail>(SPEECH_START_EVENT, { detail }));
}

export function dispatchSpeechRange(detail: SpeechRangePresentationDetail): void {
  window.dispatchEvent(new CustomEvent<SpeechRangePresentationDetail>(SPEECH_RANGE_EVENT, { detail }));
}

export function dispatchSpeechDone(detail: SpeechPresentationDetail): void {
  window.dispatchEvent(new CustomEvent<SpeechPresentationDetail>(SPEECH_DONE_EVENT, { detail }));
}

export function dispatchSpeechError(detail: SpeechPresentationDetail): void {
  window.dispatchEvent(new CustomEvent<SpeechPresentationDetail>(SPEECH_ERROR_EVENT, { detail }));
}
