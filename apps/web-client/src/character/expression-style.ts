export const EXPRESSION_STYLE_IDS = [
  "balanced",
  "playful",
  "reserved",
  "tsundere",
  "mesugaki",
  "yandere",
] as const;

export type ExpressionStyleId = (typeof EXPRESSION_STYLE_IDS)[number];

export function isExpressionStyleId(value: unknown): value is ExpressionStyleId {
  return typeof value === "string"
    && (EXPRESSION_STYLE_IDS as readonly string[]).includes(value);
}

export function defaultExpressionStyleForCharacter(
  characterId: "younghee" | "cheolsu" | null,
): ExpressionStyleId {
  if (characterId === "younghee") return "playful";
  if (characterId === "cheolsu") return "reserved";
  return "balanced";
}
