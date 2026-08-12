from pathlib import Path

BRANCH_FILES = Path("apps/web-client/src/character")


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    Path(path).write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    if old not in content:
        raise RuntimeError(f"missing patch anchor in {path}: {old[:120]!r}")
    write(path, content.replace(old, new, 1))


write(
    "apps/web-client/src/character/persona-performance-style.ts",
    '''import type { ExpressionStyleId } from "./expression-style.js";

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
''',
)

# Emotion posture consumes the same allow-listed style ID, but only as local presentation data.
replace_once(
    "apps/web-client/src/character/vrm-emotion-posture.ts",
    '''import type { HearthGhostCharacterId } from "./catalog.js";\nimport type { CharacterEmotion, CharacterState } from "./semantic.js";\n''',
    '''import type { HearthGhostCharacterId } from "./catalog.js";\nimport {\n  defaultExpressionStyleForCharacter,\n  type ExpressionStyleId,\n} from "./expression-style.js";\nimport { personaPerformanceStyleProfile } from "./persona-performance-style.js";\nimport type { CharacterEmotion, CharacterState } from "./semantic.js";\n''',
)

replace_once(
    "apps/web-client/src/character/vrm-emotion-posture.ts",
    '''}\n\n/**\n * Low-amplitude body-language overlay for semantic emotion.\n''',
    '''}\n\nfunction styleEmotionBias(\n  emotion: CharacterEmotion,\n  style: ExpressionStyleId,\n  side: number,\n): Readonly<Partial<Record<EmotionPostureBoneName, EmotionPostureRotation>>> {\n  if (style === "playful") {\n    if (emotion === "happy" || emotion === "amused" || emotion === "curious") {\n      return Object.freeze({\n        chest: [-0.003, 0.004 * side, 0.006 * side],\n        head: [-0.004, -0.004 * side, 0.010 * side],\n        leftShoulder: [0, 0, -0.006],\n        rightShoulder: [0, 0, 0.006],\n      });\n    }\n    return Object.freeze({});\n  }\n\n  if (style === "reserved") {\n    if (emotion === "embarrassed" || emotion === "concerned" || emotion === "sad") {\n      return Object.freeze({\n        chest: [0.006, -0.003 * side, 0],\n        head: [0.010, 0.004 * side, -0.004 * side],\n        leftShoulder: [0.002, 0, 0.006],\n        rightShoulder: [0.002, 0, -0.006],\n        leftUpperArm: [0.003, -0.004, -0.006],\n        rightUpperArm: [-0.003, 0.004, 0.006],\n      });\n    }\n    return Object.freeze({});\n  }\n\n  if (style === "tsundere") {\n    if (emotion === "embarrassed" || emotion === "affectionate") {\n      return Object.freeze({\n        spine: [0.004, 0.010 * side, 0],\n        chest: [0.008, 0.026 * side, -0.006 * side],\n        neck: [0.006, 0.022 * side, -0.010 * side],\n        head: [0.010, 0.052 * side, -0.026 * side],\n        leftShoulder: [0.003, 0, 0.014],\n        rightShoulder: [0.003, 0, -0.014],\n        leftUpperArm: [0.004, -0.010, -0.012],\n        rightUpperArm: [-0.004, 0.010, 0.012],\n      });\n    }\n    if (emotion === "annoyed") {\n      return Object.freeze({\n        chest: [0.002, 0.018 * side, -0.004 * side],\n        head: [0.004, 0.030 * side, -0.014 * side],\n      });\n    }\n    return Object.freeze({});\n  }\n\n  if (style === "mesugaki") {\n    if (emotion === "smug" || emotion === "amused") {\n      return Object.freeze({\n        spine: [-0.003, 0.010 * side, -0.004 * side],\n        chest: [-0.006, 0.026 * side, 0.014 * side],\n        neck: [-0.004, -0.020 * side, 0.018 * side],\n        head: [-0.006, -0.036 * side, 0.040 * side],\n        leftShoulder: [0, 0, -0.006 - 0.004 * side],\n        rightShoulder: [0, 0, 0.006 - 0.004 * side],\n      });\n    }\n    return Object.freeze({});\n  }\n\n  if (style === "yandere") {\n    if (emotion === "affectionate") {\n      return Object.freeze({\n        spine: [-0.006, 0, -0.002 * side],\n        chest: [-0.014, 0.004 * side, 0.006 * side],\n        neck: [-0.006, -0.006 * side, 0.012 * side],\n        head: [-0.012, -0.010 * side, 0.030 * side],\n        leftShoulder: [0, 0, -0.008],\n        rightShoulder: [0, 0, 0.008],\n      });\n    }\n    if (emotion === "concerned") {\n      return Object.freeze({\n        chest: [-0.006, 0, 0],\n        head: [0.006, 0.004 * side, 0.008 * side],\n      });\n    }\n  }\n\n  return Object.freeze({});\n}\n\n/**\n * Low-amplitude body-language overlay for semantic emotion.\n''',
)

replace_once(
    "apps/web-client/src/character/vrm-emotion-posture.ts",
    '''export class EmotionPostureController {\n  private readonly profile: EmotionPostureProfile;\n  private readonly current = zeroFrame();\n  private readonly target = zeroFrame();\n  private lastEmotion: CharacterEmotion = "neutral";\n  private lastState: CharacterState = "sleeping";\n\n  constructor(characterId: HearthGhostCharacterId | null = null) {\n    this.profile = characterId === null ? GENERIC_PROFILE : PROFILES[characterId];\n  }\n''',
    '''export class EmotionPostureController {\n  private readonly profile: EmotionPostureProfile;\n  private readonly current = zeroFrame();\n  private readonly target = zeroFrame();\n  private style: ExpressionStyleId;\n  private styleDirty = true;\n  private lastEmotion: CharacterEmotion = "neutral";\n  private lastState: CharacterState = "sleeping";\n\n  constructor(\n    characterId: HearthGhostCharacterId | null = null,\n    style: ExpressionStyleId = defaultExpressionStyleForCharacter(characterId),\n  ) {\n    this.profile = characterId === null ? GENERIC_PROFILE : PROFILES[characterId];\n    this.style = style;\n  }\n\n  setStyle(style: ExpressionStyleId): void {\n    if (style !== this.style) {\n      this.style = style;\n      this.styleDirty = true;\n    }\n  }\n''',
)

replace_once(
    "apps/web-client/src/character/vrm-emotion-posture.ts",
    '''  reset(): void {\n    this.lastEmotion = "neutral";\n    this.lastState = "sleeping";\n''',
    '''  reset(): void {\n    this.lastEmotion = "neutral";\n    this.lastState = "sleeping";\n    this.styleDirty = true;\n''',
)

replace_once(
    "apps/web-client/src/character/vrm-emotion-posture.ts",
    '''    if (emotion !== this.lastEmotion || state !== this.lastState) {\n      this.selectTarget(state, emotion);\n      this.lastEmotion = emotion;\n      this.lastState = state;\n    }\n''',
    '''    if (emotion !== this.lastEmotion || state !== this.lastState || this.styleDirty) {\n      this.selectTarget(state, emotion);\n      this.lastEmotion = emotion;\n      this.lastState = state;\n      this.styleDirty = false;\n    }\n''',
)

replace_once(
    "apps/web-client/src/character/vrm-emotion-posture.ts",
    '''    const influence = stateInfluence(state) * this.profile.scale;\n    if (influence === 0 || emotion === "neutral") {\n      return;\n    }\n    const target = emotionTarget(emotion, this.profile);\n    for (const [bone, rotation] of Object.entries(target) as [\n      EmotionPostureBoneName,\n      EmotionPostureRotation,\n    ][]) {\n      this.target[bone] = [\n        rotation[0] * influence,\n        rotation[1] * influence,\n        rotation[2] * influence,\n      ];\n    }\n''',
    '''    const styleProfile = personaPerformanceStyleProfile(this.style);\n    const influence = stateInfluence(state) * this.profile.scale * styleProfile.bodyScale;\n    if (influence === 0 || emotion === "neutral") {\n      return;\n    }\n    const base = emotionTarget(emotion, this.profile);\n    const bias = styleEmotionBias(\n      emotion,\n      this.style,\n      this.profile.lateralSign * this.profile.expressiveness,\n    );\n    for (const bone of BONES) {\n      const primary = base[bone];\n      const secondary = bias[bone];\n      if (primary === undefined && secondary === undefined) {\n        continue;\n      }\n      this.target[bone] = [\n        ((primary?.[0] ?? 0) + (secondary?.[0] ?? 0)) * influence,\n        ((primary?.[1] ?? 0) + (secondary?.[1] ?? 0)) * influence,\n        ((primary?.[2] ?? 0) + (secondary?.[2] ?? 0)) * influence,\n      ];\n    }\n''',
)

# Gaze controller uses style to alter choreography, never coordinates from the server/LLM.
replace_once(
    "apps/web-client/src/character/vrm-gaze-behavior.ts",
    '''import type { HearthGhostCharacterId } from "./catalog.js";\nimport type { CharacterEmotion, CharacterState } from "./semantic.js";\n''',
    '''import type { HearthGhostCharacterId } from "./catalog.js";\nimport {\n  defaultExpressionStyleForCharacter,\n  type ExpressionStyleId,\n} from "./expression-style.js";\nimport { personaPerformanceStyleProfile } from "./persona-performance-style.js";\nimport type { CharacterEmotion, CharacterState } from "./semantic.js";\n''',
)

replace_once(
    "apps/web-client/src/character/vrm-gaze-behavior.ts",
    '''  private lastState: CharacterState = "sleeping";\n  private lastEmotion: CharacterEmotion = "neutral";\n  private lastGlanceSide: "left" | "right" | null = null;\n\n  constructor(\n    characterId: HearthGhostCharacterId | null = null,\n    private readonly random: () => number = Math.random,\n  ) {\n    this.profile = characterId === null ? GENERIC_PROFILE : PROFILES[characterId];\n  }\n''',
    '''  private lastState: CharacterState = "sleeping";\n  private lastEmotion: CharacterEmotion = "neutral";\n  private lastGlanceSide: "left" | "right" | null = null;\n  private style: ExpressionStyleId;\n  private styleDirty = true;\n\n  constructor(\n    characterId: HearthGhostCharacterId | null = null,\n    private readonly random: () => number = Math.random,\n    style: ExpressionStyleId = defaultExpressionStyleForCharacter(characterId),\n  ) {\n    this.profile = characterId === null ? GENERIC_PROFILE : PROFILES[characterId];\n    this.style = style;\n  }\n\n  setStyle(style: ExpressionStyleId): void {\n    if (style !== this.style) {\n      this.style = style;\n      this.styleDirty = true;\n    }\n  }\n''',
)

replace_once(
    "apps/web-client/src/character/vrm-gaze-behavior.ts",
    '''    this.lastState = "sleeping";\n    this.lastEmotion = "neutral";\n    this.lastGlanceSide = null;\n  }\n''',
    '''    this.lastState = "sleeping";\n    this.lastEmotion = "neutral";\n    this.lastGlanceSide = null;\n    this.styleDirty = true;\n  }\n''',
)

replace_once(
    "apps/web-client/src/character/vrm-gaze-behavior.ts",
    '''    if (state !== this.lastState || emotion !== this.lastEmotion) {\n      this.onPresentationChange(elapsed, state, emotion);\n      this.lastState = state;\n      this.lastEmotion = emotion;\n    }\n''',
    '''    if (state !== this.lastState || emotion !== this.lastEmotion || this.styleDirty) {\n      this.onPresentationChange(elapsed, state, emotion);\n      this.lastState = state;\n      this.lastEmotion = emotion;\n      this.styleDirty = false;\n    }\n''',
)

replace_once(
    "apps/web-client/src/character/vrm-gaze-behavior.ts",
    '''    if (state === "thinking") {\n      this.chooseThinkingGlance(elapsed, emotion);\n      return;\n    }\n    this.returnToFocus(elapsed, state, emotion, true);\n''',
    '''    if (this.style === "tsundere" && (emotion === "embarrassed" || emotion === "affectionate")) {\n      this.startSideGlance(elapsed, 0.26, 1.46, 0.9, 1.3, 5.0);\n      return;\n    }\n    if (this.style === "reserved" && (emotion === "embarrassed" || emotion === "concerned")) {\n      this.startGlance("glance-down", 0.035 * this.sideSign(), 1.36, elapsed, 0.8, 1.2, 4.2);\n      return;\n    }\n    if (this.style === "mesugaki" && (emotion === "smug" || emotion === "amused")) {\n      this.startSideGlance(elapsed, 0.24, 1.51, 0.45, 0.85, 5.4);\n      return;\n    }\n    if (this.style === "yandere" && emotion === "affectionate") {\n      this.setTarget("focus", 0, USER_FOCUS_Y + 0.012, 5.6);\n      this.nextActionAt = elapsed + 4.8;\n      return;\n    }\n    if (state === "thinking") {\n      this.chooseThinkingGlance(elapsed, emotion);\n      return;\n    }\n    this.returnToFocus(elapsed, state, emotion, true);\n''',
)

replace_once(
    "apps/web-client/src/character/vrm-gaze-behavior.ts",
    '''    if (this.random() < clamp(glanceChance + emotionBoost, 0, 0.64)) {\n''',
    '''    const styleProfile = personaPerformanceStyleProfile(this.style);\n    if (this.random() < clamp(glanceChance + emotionBoost + styleProfile.glanceChanceBias, 0, 0.68)) {\n''',
)

replace_once(
    "apps/web-client/src/character/vrm-gaze-behavior.ts",
    '''      this.profile.thinkingDownBias + (emotion === "concerned" ? 0.24 : 0),\n''',
    '''      this.profile.thinkingDownBias\n        + personaPerformanceStyleProfile(this.style).thinkingDownBias\n        + (emotion === "concerned" ? 0.24 : 0),\n''',
)

replace_once(
    "apps/web-client/src/character/vrm-gaze-behavior.ts",
    '''    const x = (this.random() * 2 - 1) * 0.075 * this.profile.microAmplitude;\n    const y = USER_FOCUS_Y + (this.random() * 2 - 1) * 0.045 * this.profile.microAmplitude;\n''',
    '''    const amplitudeScale = personaPerformanceStyleProfile(this.style).gazeAmplitudeScale;\n    const x = (this.random() * 2 - 1) * 0.075 * this.profile.microAmplitude * amplitudeScale;\n    const y = USER_FOCUS_Y\n      + (this.random() * 2 - 1) * 0.045 * this.profile.microAmplitude * amplitudeScale;\n''',
)

replace_once(
    "apps/web-client/src/character/vrm-gaze-behavior.ts",
    '''    this.nextActionAt = elapsed + (minimum + this.random() * spread) * this.profile.intervalScale;\n''',
    '''    this.nextActionAt = elapsed\n      + (minimum + this.random() * spread)\n        * this.profile.intervalScale\n        * personaPerformanceStyleProfile(this.style).gazeIntervalScale;\n''',
)

replace_once(
    "apps/web-client/src/character/vrm-gaze-behavior.ts",
    '''      x * this.profile.amplitude,\n      USER_FOCUS_Y + (y - USER_FOCUS_Y) * this.profile.amplitude,\n''',
    '''      x * this.profile.amplitude * personaPerformanceStyleProfile(this.style).gazeAmplitudeScale,\n      USER_FOCUS_Y\n        + (y - USER_FOCUS_Y)\n          * this.profile.amplitude\n          * personaPerformanceStyleProfile(this.style).gazeAmplitudeScale,\n''',
)

# Replace the second interval calculation in returnToFocus.
content = read("apps/web-client/src/character/vrm-gaze-behavior.ts")
needle = '''    this.nextActionAt = elapsed + (minimum + this.random() * spread) * this.profile.intervalScale;\n'''
if needle not in content:
    raise RuntimeError("return-to-focus interval anchor missing")
content = content.replace(
    needle,
    '''    this.nextActionAt = elapsed\n      + (minimum + this.random() * spread)\n        * this.profile.intervalScale\n        * personaPerformanceStyleProfile(this.style).gazeIntervalScale;\n''',
    1,
)
write("apps/web-client/src/character/vrm-gaze-behavior.ts", content)

# One renderer-local setter fans the approved style out to face, body, and gaze.
replace_once(
    "apps/web-client/src/character/vrm-renderer.ts",
    '''  setExpressionStyle(style: ExpressionStyleId): void {\n    this.expressionComposer.setStyle(style);\n  }\n''',
    '''  setExpressionStyle(style: ExpressionStyleId): void {\n    this.expressionComposer.setStyle(style);\n    this.emotionPosture.setStyle(style);\n    this.gaze.setStyle(style);\n  }\n''',
)

# Tests: style changes should alter local performance without widening semantics.
with Path("apps/web-client/tests/vrm-emotion-posture.test.mjs").open("a", encoding="utf-8") as handle:
    handle.write('''\n\ntest("tsundere embarrassment turns away and closes the silhouette more than balanced", () => {\n  const balanced = new EmotionPostureController("younghee", "balanced");\n  const tsundere = new EmotionPostureController("younghee", "tsundere");\n  balanced.reset();\n  tsundere.reset();\n\n  const base = settle(balanced, "engaged", "embarrassed");\n  const styled = settle(tsundere, "engaged", "embarrassed");\n\n  assert.ok(Math.abs(styled.head[1]) > Math.abs(base.head[1]) + 0.01);\n  assert.ok(styled.leftShoulder[2] > base.leftShoulder[2]);\n  assert.ok(styled.rightShoulder[2] < base.rightShoulder[2]);\n  assert.ok(maxAbs(styled) < 0.10);\n});\n\ntest("mesugaki smug posture exaggerates the teasing head cant without large rotations", () => {\n  const balanced = new EmotionPostureController("younghee", "balanced");\n  const styled = new EmotionPostureController("younghee", "mesugaki");\n  balanced.reset();\n  styled.reset();\n\n  const base = settle(balanced, "engaged", "smug");\n  const frame = settle(styled, "engaged", "smug");\n\n  assert.ok(Math.abs(frame.head[2]) > Math.abs(base.head[2]));\n  assert.ok(Math.abs(frame.chest[1]) > Math.abs(base.chest[1]));\n  assert.ok(maxAbs(frame) < 0.10);\n});\n\ntest("yandere affection leans in locally while remaining a rotation-only overlay", () => {\n  const balanced = new EmotionPostureController("younghee", "balanced");\n  const styled = new EmotionPostureController("younghee", "yandere");\n  balanced.reset();\n  styled.reset();\n\n  const base = settle(balanced, "engaged", "affectionate");\n  const frame = settle(styled, "engaged", "affectionate");\n\n  assert.ok(frame.chest[0] < base.chest[0]);\n  assert.ok(Math.abs(frame.head[2]) > Math.abs(base.head[2]));\n  assert.deepEqual(Object.keys(frame).sort(), Object.keys(base).sort());\n});\n\ntest("changing persona style reselects body language without changing semantic emotion", () => {\n  const controller = new EmotionPostureController("younghee", "balanced");\n  controller.reset();\n  const before = settle(controller, "engaged", "embarrassed");\n  const yawBefore = before.head[1];\n\n  controller.setStyle("tsundere");\n  const first = controller.update(1 / 60, "engaged", "embarrassed");\n  assert.ok(Math.abs(first.head[1] - yawBefore) < 0.01);\n  const after = settle(controller, "engaged", "embarrassed");\n  assert.ok(Math.abs(after.head[1]) > Math.abs(yawBefore));\n});\n''')

with Path("apps/web-client/tests/vrm-gaze-behavior.test.mjs").open("a", encoding="utf-8") as handle:
    handle.write('''\n\ntest("tsundere embarrassment performs a deliberate side glance", () => {\n  const gaze = new GazeBehaviorController("younghee", sequence([0.2, 0.5, 0.4]), "tsundere");\n  gaze.reset(0);\n  const frame = settle(gaze, 0, "engaged", "embarrassed", 0.8);\n\n  assert.match(frame.behavior, /^glance-(left|right)$/);\n  assert.ok(Math.abs(frame.x) > 0.10);\n});\n\ntest("reserved embarrassment lowers the gaze instead of seeking a large side glance", () => {\n  const gaze = new GazeBehaviorController("cheolsu", sequence([0.4, 0.5, 0.6]), "reserved");\n  gaze.reset(0);\n  const frame = settle(gaze, 0, "engaged", "embarrassed", 0.8);\n\n  assert.equal(frame.behavior, "glance-down");\n  assert.ok(frame.y < 1.43);\n});\n\ntest("mesugaki smug presentation uses a short teasing side glance", () => {\n  const gaze = new GazeBehaviorController("younghee", sequence([0.8, 0.5, 0.3]), "mesugaki");\n  gaze.reset(0);\n  const frame = settle(gaze, 0, "engaged", "smug", 0.4);\n\n  assert.match(frame.behavior, /^glance-(left|right)$/);\n  assert.ok(Math.abs(frame.x) > 0.10);\n});\n\ntest("yandere affection holds user focus longer without inventing a semantic action", () => {\n  const gaze = new GazeBehaviorController("younghee", sequence([0.1, 0.9, 0.2]), "yandere");\n  gaze.reset(0);\n  let frame = settle(gaze, 0, "engaged", "affectionate", 1.0);\n  assert.equal(frame.behavior, "focus");\n  assert.ok(Math.abs(frame.x) < 0.02);\n\n  frame = gaze.update(1 / 60, 3.5, "engaged", "affectionate");\n  assert.equal(frame.behavior, "focus");\n});\n\ntest("style swap immediately reselects gaze choreography for the same emotion", () => {\n  const gaze = new GazeBehaviorController("younghee", sequence([0.2, 0.4, 0.6]), "balanced");\n  gaze.reset(0);\n  settle(gaze, 0, "engaged", "embarrassed", 0.2);\n\n  gaze.setStyle("tsundere");\n  const frame = gaze.update(1 / 60, 0.25, "engaged", "embarrassed");\n  assert.match(frame.behavior, /^glance-(left|right)$/);\n});\n''')
