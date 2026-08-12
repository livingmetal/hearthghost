export const RESPONSE_REVEAL_START_EVENT = "hearthghost:response-reveal-start";
export const RESPONSE_REVEAL_PROGRESS_EVENT = "hearthghost:response-reveal-progress";
export const RESPONSE_REVEAL_DONE_EVENT = "hearthghost:response-reveal-done";

export interface ResponseRevealDetail {
  readonly text: string;
}

export interface ResponseRevealProgressDetail extends ResponseRevealDetail {
  readonly end: number;
}
