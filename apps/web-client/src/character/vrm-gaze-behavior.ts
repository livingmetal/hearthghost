import type { HearthGhostCharacterId } from "./catalog.js";
import type { CharacterEmotion, CharacterState } from "./semantic.js";

export type GazeBehaviorName =
  | "focus"
  | "micro"
  | "glance-left"
  | "glance-right"
  | "glance-up"
  | "glance-down";

export interface VrmGazeFrame {
  readonly x: number;
  readonly y: number;
  readonly response: number;
  readonly behavior: GazeBehaviorName;
}

interface GazeProfile {
  readonly amplitude: number;
  readonly microAmplitude: number;
  readonly intervalScale: number;
  readonly thinkingDownBias: number;
}

const PROFILES: Readonly<Record<HearthGhostCharacterId, GazeProfile>> = Object.freeze({
  younghee: Object.freeze({
    amplitude: 1.0,
    microAmplitude: 1.0,
    intervalScale: 0.88,
    thinkingDownBias: 0.20,
  }),
  cheolsu: Object.freeze({
    amplitude: 0.76,
    microAmplitude: 0.72,
    intervalScale: 1.20,
    thinkingDownBias: 0.42,
  }),
});

const GENERIC_PROFILE: GazeProfile = Object.freeze({
  amplitude: 0.82,
  microAmplitude: 0.80,
  intervalScale: 1.0,
  thinkingDownBias: 0.30,
});

const USER_FOCUS_Y = 1.48;

function approach(current: number, target: number, response: number, delta: number): number {
  const blend = 1 - Math.exp(-response * Math.max(0, Math.min(delta, 0.1)));
  return current + (target - current) * blend;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, value));
}

/**
 * Presentation-only gaze performance. It never changes semantic state and never
 * exposes coordinates to the model. The controller alternates user focus with
 * bounded micro-saccades and short glance-away/return sequences.
 */
export class GazeBehaviorController {
  private readonly profile: GazeProfile;
  private currentX = 0;
  private currentY = USER_FOCUS_Y;
  private targetX = 0;
  private targetY = USER_FOCUS_Y;
  private response = 4.5;
  private behavior: GazeBehaviorName = "focus";
  private nextActionAt = 0;
  private glanceEndsAt = 0;
  private lastState: CharacterState = "sleeping";
  private lastEmotion: CharacterEmotion = "neutral";
  private lastGlanceSide: "left" | "right" | null = null;

  constructor(
    characterId: HearthGhostCharacterId | null = null,
    private readonly random: () => number = Math.random,
  ) {
    this.profile = characterId === null ? GENERIC_PROFILE : PROFILES[characterId];
  }

  reset(elapsed = 0): void {
    this.currentX = 0;
    this.currentY = USER_FOCUS_Y;
    this.targetX = 0;
    this.targetY = USER_FOCUS_Y;
    this.response = 4.5;
    this.behavior = "focus";
    this.nextActionAt = elapsed;
    this.glanceEndsAt = elapsed;
    this.lastState = "sleeping";
    this.lastEmotion = "neutral";
    this.lastGlanceSide = null;
  }

  update(
    delta: number,
    elapsed: number,
    state: CharacterState,
    emotion: CharacterEmotion,
  ): VrmGazeFrame {
    if (state !== this.lastState || emotion !== this.lastEmotion) {
      this.onPresentationChange(elapsed, state, emotion);
      this.lastState = state;
      this.lastEmotion = emotion;
    }

    if (state === "sleeping") {
      this.setTarget("focus", 0, 1.28, 2.5);
    } else if (emotion === "surprised" || state === "noticing") {
      this.setTarget("focus", 0, USER_FOCUS_Y, 7.0);
      this.nextActionAt = Math.max(this.nextActionAt, elapsed + 0.8);
    } else if (this.behavior !== "focus" && this.behavior !== "micro" && elapsed >= this.glanceEndsAt) {
      this.returnToFocus(elapsed, state, emotion);
    } else if (elapsed >= this.nextActionAt) {
      this.chooseNextAction(elapsed, state, emotion);
    }

    this.currentX = approach(this.currentX, this.targetX, this.response, delta);
    this.currentY = approach(this.currentY, this.targetY, this.response, delta);

    return Object.freeze({
      x: this.currentX,
      y: this.currentY,
      response: this.response,
      behavior: this.behavior,
    });
  }

  private onPresentationChange(
    elapsed: number,
    state: CharacterState,
    emotion: CharacterEmotion,
  ): void {
    if (state === "sleeping") {
      this.setTarget("focus", 0, 1.28, 2.5);
      this.nextActionAt = elapsed + 4;
      return;
    }
    if (state === "noticing" || emotion === "surprised") {
      this.setTarget("focus", 0, USER_FOCUS_Y, 7.0);
      this.nextActionAt = elapsed + 0.9;
      return;
    }
    if (state === "thinking") {
      this.chooseThinkingGlance(elapsed, emotion);
      return;
    }
    this.returnToFocus(elapsed, state, emotion, true);
  }

  private chooseNextAction(
    elapsed: number,
    state: CharacterState,
    emotion: CharacterEmotion,
  ): void {
    if (state === "thinking") {
      this.chooseThinkingGlance(elapsed, emotion);
      return;
    }

    const glanceChance = state === "engaged"
      ? 0.42
      : state === "listening"
        ? 0.24
        : state === "speaking"
          ? 0.12
          : 0.08;
    const emotionBoost = emotion === "curious"
      ? 0.16
      : emotion === "amused"
        ? 0.08
        : emotion === "concerned"
          ? 0.05
          : 0;

    if (this.random() < clamp(glanceChance + emotionBoost, 0, 0.64)) {
      this.chooseAmbientGlance(elapsed, state, emotion);
    } else {
      this.chooseMicroSaccade(elapsed, state);
    }
  }

  private chooseThinkingGlance(elapsed: number, emotion: CharacterEmotion): void {
    const roll = this.random();
    const downBias = clamp(
      this.profile.thinkingDownBias + (emotion === "concerned" ? 0.24 : 0),
      0.12,
      0.72,
    );

    if (roll < downBias) {
      this.startGlance("glance-down", 0.05 * this.sideSign(), 1.34, elapsed, 0.9, 1.65, 4.2);
      return;
    }
    if (roll > 0.78 && emotion !== "concerned") {
      this.startGlance("glance-up", 0.16 * this.sideSign(), 1.61, elapsed, 0.9, 1.55, 4.0);
      return;
    }
    this.startSideGlance(elapsed, 0.23, 1.50, 1.0, 1.75, 4.0);
  }

  private chooseAmbientGlance(
    elapsed: number,
    state: CharacterState,
    emotion: CharacterEmotion,
  ): void {
    if (emotion === "concerned" && this.random() < 0.58) {
      this.startGlance("glance-down", 0.04 * this.sideSign(), 1.38, elapsed, 0.55, 1.00, 4.6);
      return;
    }
    if (emotion === "curious" && this.random() < 0.42) {
      this.startGlance("glance-up", 0.12 * this.sideSign(), 1.57, elapsed, 0.55, 0.95, 4.8);
      return;
    }
    const amplitude = state === "engaged" ? 0.20 : 0.15;
    this.startSideGlance(elapsed, amplitude, USER_FOCUS_Y, 0.45, 0.92, 4.8);
  }

  private chooseMicroSaccade(elapsed: number, state: CharacterState): void {
    const x = (this.random() * 2 - 1) * 0.075 * this.profile.microAmplitude;
    const y = USER_FOCUS_Y + (this.random() * 2 - 1) * 0.045 * this.profile.microAmplitude;
    this.setTarget("micro", x, y, 5.4);
    const [minimum, spread] = state === "speaking" ? [0.75, 1.55] : [1.0, 2.2];
    this.nextActionAt = elapsed + (minimum + this.random() * spread) * this.profile.intervalScale;
  }

  private startSideGlance(
    elapsed: number,
    amplitude: number,
    y: number,
    minimumHold: number,
    holdSpread: number,
    response: number,
  ): void {
    const side = this.nextSide();
    const name = side === "left" ? "glance-left" : "glance-right";
    const sign = side === "left" ? -1 : 1;
    this.startGlance(name, sign * amplitude, y, elapsed, minimumHold, holdSpread, response);
  }

  private startGlance(
    behavior: Exclude<GazeBehaviorName, "focus" | "micro">,
    x: number,
    y: number,
    elapsed: number,
    minimumHold: number,
    holdSpread: number,
    response: number,
  ): void {
    this.setTarget(
      behavior,
      x * this.profile.amplitude,
      USER_FOCUS_Y + (y - USER_FOCUS_Y) * this.profile.amplitude,
      response,
    );
    this.glanceEndsAt = elapsed + minimumHold + this.random() * holdSpread;
    this.nextActionAt = this.glanceEndsAt;
  }

  private returnToFocus(
    elapsed: number,
    state: CharacterState,
    emotion: CharacterEmotion,
    immediate = false,
  ): void {
    const concernedDrop = emotion === "concerned" ? -0.025 : 0;
    this.setTarget("focus", 0, USER_FOCUS_Y + concernedDrop, immediate ? 5.8 : 5.2);
    const [minimum, spread] = state === "engaged"
      ? [2.1, 3.2]
      : state === "listening"
        ? [2.6, 3.5]
        : state === "speaking"
          ? [1.5, 2.6]
          : [1.7, 2.8];
    this.nextActionAt = elapsed + (minimum + this.random() * spread) * this.profile.intervalScale;
  }

  private setTarget(
    behavior: GazeBehaviorName,
    x: number,
    y: number,
    response: number,
  ): void {
    this.behavior = behavior;
    this.targetX = clamp(x, -0.30, 0.30);
    this.targetY = clamp(y, 1.30, 1.64);
    this.response = response;
  }

  private nextSide(): "left" | "right" {
    let side: "left" | "right" = this.random() < 0.5 ? "left" : "right";
    if (side === this.lastGlanceSide) {
      side = side === "left" ? "right" : "left";
    }
    this.lastGlanceSide = side;
    return side;
  }

  private sideSign(): number {
    return this.nextSide() === "left" ? -1 : 1;
  }
}
