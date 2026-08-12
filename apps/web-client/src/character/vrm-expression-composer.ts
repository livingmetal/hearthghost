import type { HearthGhostCharacterId } from "./catalog.js";
import {
  defaultExpressionStyleForCharacter,
  type ExpressionStyleId,
} from "./expression-style.js";
import type { CharacterEmotion, CharacterState } from "./semantic.js";

export { EXPRESSION_STYLE_IDS } from "./expression-style.js";
export { defaultExpressionStyleForCharacter };
export type { ExpressionStyleId };

type LogicalExpressionChannel =
  | "happy"
  | "angry"
  | "sad"
  | "relaxed"
  | "surprised"
  | "smirk"
  | "blush"
  | "annoyed"
  | "affection";

interface ExpressionStyleProfile {
  readonly overallScale: number;
  readonly happyScale: number;
  readonly angryScale: number;
  readonly sadScale: number;
  readonly relaxedScale: number;
  readonly surprisedScale: number;
  readonly customScale: number;
  readonly attackResponse: number;
  readonly releaseResponse: number;
}

export type ExpressionTarget = Readonly<Record<string, number>>;

const RESERVED_EXPRESSION_NAMES = new Set([
  "blink",
  "blinkleft",
  "blinkright",
  "lookup",
  "lookdown",
  "lookleft",
  "lookright",
  "aa",
  "ih",
  "ou",
  "ee",
  "oh",
]);

const STANDARD_CHANNELS = new Set<LogicalExpressionChannel>([
  "happy",
  "angry",
  "sad",
  "relaxed",
  "surprised",
]);

const CUSTOM_ALIASES: Readonly<
  Record<Exclude<LogicalExpressionChannel, "happy" | "angry" | "sad" | "relaxed" | "surprised">, readonly string[]>
> = Object.freeze({
  smirk: Object.freeze(["smirk", "smug", "grin"]),
  blush: Object.freeze(["blush", "shy", "embarrassed"]),
  annoyed: Object.freeze(["annoyed", "irritated"]),
  affection: Object.freeze(["affection", "affectionate", "love", "heart"]),
});

const BASE_RECIPES: Readonly<
  Record<CharacterEmotion, Readonly<Partial<Record<LogicalExpressionChannel, number>>>>
> = Object.freeze({
  neutral: Object.freeze({}),
  happy: Object.freeze({ happy: 0.48, relaxed: 0.08 }),
  amused: Object.freeze({ happy: 0.36, relaxed: 0.14, smirk: 0.20 }),
  curious: Object.freeze({ surprised: 0.13, happy: 0.05, relaxed: 0.04 }),
  concerned: Object.freeze({ sad: 0.27, relaxed: 0.04 }),
  surprised: Object.freeze({ surprised: 0.58 }),
  angry: Object.freeze({ angry: 0.50, sad: 0.04 }),
  sad: Object.freeze({ sad: 0.50, relaxed: 0.04 }),
  annoyed: Object.freeze({ angry: 0.29, sad: 0.05, annoyed: 0.26 }),
  embarrassed: Object.freeze({ happy: 0.10, sad: 0.13, relaxed: 0.08, blush: 0.44 }),
  smug: Object.freeze({ happy: 0.24, relaxed: 0.08, smirk: 0.52 }),
  affectionate: Object.freeze({ happy: 0.39, relaxed: 0.22, blush: 0.18, affection: 0.26 }),
});

const STYLE_PROFILES: Readonly<Record<ExpressionStyleId, ExpressionStyleProfile>> = Object.freeze({
  balanced: Object.freeze({
    overallScale: 1.0,
    happyScale: 1.0,
    angryScale: 1.0,
    sadScale: 1.0,
    relaxedScale: 1.0,
    surprisedScale: 1.0,
    customScale: 1.0,
    attackResponse: 7.0,
    releaseResponse: 5.0,
  }),
  playful: Object.freeze({
    overallScale: 1.02,
    happyScale: 1.08,
    angryScale: 0.92,
    sadScale: 0.94,
    relaxedScale: 1.04,
    surprisedScale: 1.08,
    customScale: 1.16,
    attackResponse: 7.8,
    releaseResponse: 5.4,
  }),
  reserved: Object.freeze({
    overallScale: 0.80,
    happyScale: 0.92,
    angryScale: 0.88,
    sadScale: 0.94,
    relaxedScale: 1.02,
    surprisedScale: 0.78,
    customScale: 0.66,
    attackResponse: 5.8,
    releaseResponse: 4.4,
  }),
  tsundere: Object.freeze({
    overallScale: 0.94,
    happyScale: 0.80,
    angryScale: 1.14,
    sadScale: 0.96,
    relaxedScale: 0.86,
    surprisedScale: 0.92,
    customScale: 1.20,
    attackResponse: 7.2,
    releaseResponse: 4.8,
  }),
  mesugaki: Object.freeze({
    overallScale: 1.0,
    happyScale: 0.96,
    angryScale: 0.90,
    sadScale: 0.78,
    relaxedScale: 0.92,
    surprisedScale: 0.92,
    customScale: 1.38,
    attackResponse: 8.2,
    releaseResponse: 5.8,
  }),
  yandere: Object.freeze({
    overallScale: 0.94,
    happyScale: 0.92,
    angryScale: 0.92,
    sadScale: 1.02,
    relaxedScale: 1.16,
    surprisedScale: 0.78,
    customScale: 1.16,
    attackResponse: 6.0,
    releaseResponse: 3.8,
  }),
});

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function styleScale(channel: LogicalExpressionChannel, profile: ExpressionStyleProfile): number {
  switch (channel) {
    case "happy":
      return profile.happyScale;
    case "angry":
      return profile.angryScale;
    case "sad":
      return profile.sadScale;
    case "relaxed":
      return profile.relaxedScale;
    case "surprised":
      return profile.surprisedScale;
    default:
      return profile.customScale;
  }
}

function addLogical(
  target: Partial<Record<LogicalExpressionChannel, number>>,
  channel: LogicalExpressionChannel,
  value: number,
): void {
  target[channel] = (target[channel] ?? 0) + value;
}

function applyStyleBias(
  target: Partial<Record<LogicalExpressionChannel, number>>,
  emotion: CharacterEmotion,
  style: ExpressionStyleId,
): void {
  if (style === "tsundere") {
    if (emotion === "embarrassed") {
      addLogical(target, "angry", 0.10);
      addLogical(target, "blush", 0.18);
    } else if (emotion === "affectionate") {
      addLogical(target, "angry", 0.07);
      addLogical(target, "blush", 0.22);
    }
    return;
  }

  if (style === "mesugaki") {
    if (emotion === "smug") {
      addLogical(target, "smirk", 0.24);
      addLogical(target, "happy", 0.06);
    } else if (emotion === "amused") {
      addLogical(target, "smirk", 0.18);
    } else if (emotion === "annoyed") {
      addLogical(target, "smirk", 0.08);
    }
    return;
  }

  if (style === "yandere") {
    if (emotion === "affectionate") {
      addLogical(target, "happy", 0.08);
      addLogical(target, "relaxed", 0.12);
      addLogical(target, "affection", 0.22);
    } else if (emotion === "concerned") {
      addLogical(target, "sad", 0.05);
      addLogical(target, "relaxed", 0.08);
    }
  }
}

function resolveExpressionName(
  channel: LogicalExpressionChannel,
  capabilities: ReadonlySet<string>,
): string | null {
  if (STANDARD_CHANNELS.has(channel)) {
    return capabilities.has(channel) ? channel : null;
  }
  const aliases = CUSTOM_ALIASES[channel as keyof typeof CUSTOM_ALIASES];
  for (const alias of aliases) {
    if (capabilities.has(alias) && !RESERVED_EXPRESSION_NAMES.has(alias)) {
      return alias;
    }
  }
  return null;
}

export function composeExpressionTarget(
  emotion: CharacterEmotion,
  style: ExpressionStyleId,
  availableExpressionNames: Iterable<string>,
): ExpressionTarget {
  const capabilities = new Set<string>();
  for (const name of availableExpressionNames) {
    const normalized = name.toLowerCase();
    if (!RESERVED_EXPRESSION_NAMES.has(normalized)) {
      capabilities.add(normalized);
    }
  }

  const logical: Partial<Record<LogicalExpressionChannel, number>> = {
    ...BASE_RECIPES[emotion],
  };
  applyStyleBias(logical, emotion, style);

  const profile = STYLE_PROFILES[style];
  const physical: Record<string, number> = {};
  for (const [channel, rawValue] of Object.entries(logical) as [LogicalExpressionChannel, number][]) {
    const actual = resolveExpressionName(channel, capabilities);
    if (actual === null) {
      continue;
    }
    physical[actual] = clamp01(
      (physical[actual] ?? 0)
      + rawValue * styleScale(channel, profile) * profile.overallScale,
    );
  }
  return Object.freeze(physical);
}

/**
 * Presentation-local facial expression composer.
 *
 * Semantic emotion stays renderer-agnostic. This controller maps that meaning
 * through a local character/persona style and the expressions actually present
 * on the loaded VRM. It never drives blink, gaze, lip-sync vowels, bones, or
 * scene transforms. Missing custom expressions simply fall back to the standard
 * preset mixture already present in the emotion recipe.
 */
export class VrmExpressionComposer {
  private capabilities = new Set<string>();
  private readonly current = new Map<string, number>();
  private style: ExpressionStyleId;

  constructor(
    characterId: HearthGhostCharacterId | null = null,
    style: ExpressionStyleId = defaultExpressionStyleForCharacter(characterId),
  ) {
    this.style = style;
  }

  getStyle(): ExpressionStyleId {
    return this.style;
  }

  setStyle(style: ExpressionStyleId): void {
    this.style = style;
  }

  setCapabilities(names: Iterable<string>): void {
    this.capabilities = new Set<string>();
    for (const name of names) {
      const normalized = name.toLowerCase();
      if (!RESERVED_EXPRESSION_NAMES.has(normalized)) {
        this.capabilities.add(normalized);
      }
    }
  }

  reset(): void {
    this.current.clear();
  }

  update(
    delta: number,
    state: CharacterState,
    emotion: CharacterEmotion,
  ): ReadonlyMap<string, number> {
    const target: ExpressionTarget = state === "sleeping"
      ? Object.freeze({})
      : composeExpressionTarget(emotion, this.style, this.capabilities);
    const profile = STYLE_PROFILES[this.style];
    const keys = new Set([...this.current.keys(), ...Object.keys(target)]);
    const boundedDelta = Math.max(0, Math.min(delta, 0.1));

    for (const name of keys) {
      const from = this.current.get(name) ?? 0;
      const to = target[name] ?? 0;
      const response = to > from ? profile.attackResponse : profile.releaseResponse;
      const blend = 1 - Math.exp(-response * boundedDelta);
      this.current.set(name, clamp01(from + (to - from) * blend));
    }
    return this.current;
  }
}
