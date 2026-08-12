import type { ExpressionStyleId } from "./expression-style.js";

export interface PersonaPerformanceStyleProfile {
  readonly bodyScale: number;
  readonly gazeAmplitudeScale: number;
  readonly gazeIntervalScale: number;
  readonly glanceChanceBias: number;
  readonly thinkingDownBias: number;
}

const PROFILES: Readonly<Record<ExpressionStyleId, PersonaPerformanceStyleProfile>> = Object.freeze({
  balanced: Object.freeze({
    bodyScale: 1.0,
    gazeAmplitudeScale: 1.0,
    gazeIntervalScale: 1.0,
    glanceChanceBias: 0,
    thinkingDownBias: 0,
  }),
  playful: Object.freeze({
    bodyScale: 1.06,
    gazeAmplitudeScale: 1.08,
    gazeIntervalScale: 0.84,
    glanceChanceBias: 0.08,
    thinkingDownBias: -0.05,
  }),
  reserved: Object.freeze({
    bodyScale: 0.80,
    gazeAmplitudeScale: 0.78,
    gazeIntervalScale: 1.18,
    glanceChanceBias: -0.06,
    thinkingDownBias: 0.14,
  }),
  tsundere: Object.freeze({
    bodyScale: 0.98,
    gazeAmplitudeScale: 1.04,
    gazeIntervalScale: 0.96,
    glanceChanceBias: 0.06,
    thinkingDownBias: 0.04,
  }),
  mesugaki: Object.freeze({
    bodyScale: 1.04,
    gazeAmplitudeScale: 1.10,
    gazeIntervalScale: 0.78,
    glanceChanceBias: 0.14,
    thinkingDownBias: -0.08,
  }),
  yandere: Object.freeze({
    bodyScale: 0.94,
    gazeAmplitudeScale: 0.86,
    gazeIntervalScale: 1.34,
    glanceChanceBias: -0.14,
    thinkingDownBias: 0.02,
  }),
});

export function personaPerformanceStyleProfile(
  style: ExpressionStyleId,
): PersonaPerformanceStyleProfile {
  return PROFILES[style];
}
