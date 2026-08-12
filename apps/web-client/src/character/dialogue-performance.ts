import type { CharacterEmotion, CharacterGesture } from "./semantic.js";
import type { CharacterExperienceController } from "./experience.js";
import {
  RESPONSE_REVEAL_DONE_EVENT,
  RESPONSE_REVEAL_PROGRESS_EVENT,
  RESPONSE_REVEAL_START_EVENT,
  type ResponseRevealDetail,
  type ResponseRevealProgressDetail,
} from "./performance-events.js";

export interface DialoguePerformanceBeat {
  readonly offset: number;
  readonly emotion: CharacterEmotion;
  readonly gesture: CharacterGesture | null;
}

export interface DialoguePerformancePlan {
  readonly text: string;
  readonly beats: readonly DialoguePerformanceBeat[];
}

const MAX_BEATS = 8;
const MIN_CLAUSE_LENGTH = 18;

const AFFECTIONATE = /(?:사랑|좋아해|고마워|반가워|소중|보고\s*싶|love\b|thank\s*you)/iu;
const EMBARRASSED = /(?:부끄|민망|쑥스|창피|embarrass|shy\b)/iu;
const ANGRY = /(?:화나|화가\s*나|분노|열받|angry|furious)/iu;
const ANNOYED = /(?:짜증|귀찮|됐거든|아니거든|annoy|irritat)/iu;
const SAD = /(?:슬프|속상|안타깝|유감|sad\b|sorry\s+to\s+hear)/iu;
const CONCERNED = /(?:걱정|조심|주의|위험|괜찮|문제|불안|아프|careful|warning|worr)/iu;
const SURPRISED = /(?:놀라|대박|헉|세상에|와[!！]|wow\b|surpris)/iu;
const AMUSED = /(?:ㅋㅋ|ㅎㅎ|하하|웃|재밌|농담|풋|haha|lol\b|funny)/iu;
const SMUG = /(?:역시|내가\s*(?:말했|그랬)|그럴\s*줄|알고\s*있었|그렇지[?？]?|told\s+you)/iu;
const HAPPY = /(?:축하|잘했|해냈|성공|다행|기쁘|좋네|멋지|congrat|well\s+done|great\b|nice\b)/iu;
const CURIOUS = /(?:궁금|왜\b|어떻게|뭘까|무엇일까|wonder|how\b|why\b)/iu;

const CLAP_CUE = /(?:축하|잘했|해냈|성공했|congrat|well\s+done)/iu;
const NOD_CUE = /^(?:맞아|그래[,.!！]?|그렇지[,.!！]?|맞습니다|그렇습니다|exactly\b|right\b)/iu;
const SHAKE_CUE = /^(?:아니야|아닙니다|안\s*돼|그건\s*아니|no[,! ]|not\s+quite)/iu;
const SHRUG_CUE = /(?:모르겠|확실하지\s*않|어쩔\s*수\s*없|not\s+sure|uncertain)/iu;
const EMBODIED_ACK = /(?:이렇게\s*할게|이렇게\s*해볼게|like\s+this)/iu;

function inferEmotion(segment: string): CharacterEmotion {
  if (AFFECTIONATE.test(segment)) return "affectionate";
  if (EMBARRASSED.test(segment)) return "embarrassed";
  if (ANGRY.test(segment)) return "angry";
  if (ANNOYED.test(segment)) return "annoyed";
  if (SAD.test(segment)) return "sad";
  if (CONCERNED.test(segment)) return "concerned";
  if (SURPRISED.test(segment)) return "surprised";
  if (AMUSED.test(segment)) return "amused";
  if (SMUG.test(segment)) return "smug";
  if (HAPPY.test(segment)) return "happy";
  if (CURIOUS.test(segment) || /[?？]\s*$/u.test(segment)) return "curious";
  if (/[!！]\s*$/u.test(segment)) return "happy";
  return "neutral";
}

function inferGesture(segment: string, fullText: string): CharacterGesture | null {
  if (EMBODIED_ACK.test(fullText)) return null;
  if (CLAP_CUE.test(segment)) return Object.freeze({ gesture: "clap" });
  if (NOD_CUE.test(segment)) return Object.freeze({ gesture: "nod" });
  if (SHAKE_CUE.test(segment)) return Object.freeze({ gesture: "shake_head" });
  if (SHRUG_CUE.test(segment)) return Object.freeze({ gesture: "shrug" });
  return null;
}

interface DialogueSegment {
  readonly start: number;
  readonly end: number;
  readonly text: string;
}

function segmentDialogue(text: string): readonly DialogueSegment[] {
  const segments: DialogueSegment[] = [];
  let start = 0;
  let lastBoundary = 0;

  const push = (end: number): void => {
    if (end <= start) return;
    const raw = text.slice(start, end);
    const leading = raw.length - raw.trimStart().length;
    const trimmed = raw.trim();
    if (trimmed !== "") {
      segments.push(Object.freeze({ start: start + leading, end, text: trimmed }));
    }
    start = end;
    lastBoundary = end;
  };

  for (let index = 0; index < text.length && segments.length < MAX_BEATS - 1; index += 1) {
    const character = text[index]!;
    const sentenceBoundary = /[.!?。！？\n]/u.test(character);
    const clauseBoundary = /[,，;；:：]/u.test(character) && index + 1 - lastBoundary >= MIN_CLAUSE_LENGTH;
    if (sentenceBoundary || clauseBoundary) {
      push(index + 1);
    }
  }
  push(text.length);
  return Object.freeze(segments);
}

export function planDialoguePerformance(text: string): DialoguePerformancePlan {
  const normalized = text.trim();
  if (normalized === "") {
    return Object.freeze({ text: "", beats: Object.freeze([]) });
  }

  const segments = segmentDialogue(normalized);
  const beats: DialoguePerformanceBeat[] = [];
  let automaticGestureUsed = false;
  let previousEmotion: CharacterEmotion | null = null;

  for (const segment of segments) {
    const emotion = inferEmotion(segment.text);
    let gesture: CharacterGesture | null = null;
    if (!automaticGestureUsed) {
      gesture = inferGesture(segment.text, normalized);
      automaticGestureUsed = gesture !== null;
    }
    if (emotion === previousEmotion && gesture === null && beats.length > 0) {
      continue;
    }
    beats.push(Object.freeze({ offset: segment.start, emotion, gesture }));
    previousEmotion = emotion;
  }

  if (beats.length === 0) {
    beats.push(Object.freeze({ offset: 0, emotion: "neutral", gesture: null }));
  } else if (beats[0]!.offset !== 0) {
    beats.unshift(Object.freeze({ offset: 0, emotion: beats[0]!.emotion, gesture: null }));
  }

  return Object.freeze({ text: normalized, beats: Object.freeze(beats.slice(0, MAX_BEATS)) });
}

function sameText(left: string, right: string): boolean {
  return left.trim() === right.trim();
}

/**
 * Synchronizes local character performance to the text that is actually visible.
 * The planner is deterministic and presentation-only: it cannot translate the
 * avatar root, address devices, or inject renderer parameters.
 */
export class DialoguePerformanceController {
  private plan: DialoguePerformancePlan | null = null;
  private nextBeat = 0;
  private installed = false;

  constructor(private readonly character: CharacterExperienceController) {}

  install(): void {
    if (this.installed) return;
    this.installed = true;
    window.addEventListener(RESPONSE_REVEAL_START_EVENT, this.onStart as EventListener);
    window.addEventListener(RESPONSE_REVEAL_PROGRESS_EVENT, this.onProgress as EventListener);
    window.addEventListener(RESPONSE_REVEAL_DONE_EVENT, this.onDone as EventListener);
  }

  dispose(): void {
    if (!this.installed) return;
    this.installed = false;
    window.removeEventListener(RESPONSE_REVEAL_START_EVENT, this.onStart as EventListener);
    window.removeEventListener(RESPONSE_REVEAL_PROGRESS_EVENT, this.onProgress as EventListener);
    window.removeEventListener(RESPONSE_REVEAL_DONE_EVENT, this.onDone as EventListener);
    this.plan = null;
    this.nextBeat = 0;
  }

  private readonly onStart = (event: CustomEvent<ResponseRevealDetail>): void => {
    this.plan = planDialoguePerformance(event.detail.text);
    this.nextBeat = 0;
    if (this.plan.text === "") return;
    this.character.beginSpeaking();
    this.applyThrough(0);
  };

  private readonly onProgress = (event: CustomEvent<ResponseRevealProgressDetail>): void => {
    if (this.plan === null || !sameText(this.plan.text, event.detail.text)) return;
    this.applyThrough(event.detail.end);
  };

  private readonly onDone = (event: CustomEvent<ResponseRevealDetail>): void => {
    if (this.plan === null || !sameText(this.plan.text, event.detail.text)) return;
    const last = this.plan.beats[this.plan.beats.length - 1];
    if (last !== undefined && this.nextBeat < this.plan.beats.length) {
      this.character.express(last.emotion);
    }
    this.character.engage();
    this.plan = null;
    this.nextBeat = 0;
  };

  private applyThrough(end: number): void {
    const plan = this.plan;
    if (plan === null) return;
    while (this.nextBeat < plan.beats.length) {
      const beat = plan.beats[this.nextBeat]!;
      if (beat.offset > end) break;
      this.character.express(beat.emotion);
      if (beat.gesture !== null) {
        this.character.performGesture(beat.gesture);
      }
      this.nextBeat += 1;
    }
  }
}
