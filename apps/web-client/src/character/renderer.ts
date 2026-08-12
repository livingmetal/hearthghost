import type { ExpressionStyleId } from "./expression-style.js";
import type { CharacterGesture, CharacterPresentation } from "./semantic.js";

export interface CharacterRenderer {
  mount(viewport: HTMLElement): Promise<void>;
  resize(width: number, height: number, pixelRatio: number): void;
  present(presentation: CharacterPresentation): void;
  setExpressionStyle?(style: ExpressionStyleId): void;
  performGesture?(gesture: CharacterGesture): void;
  suspend(): void;
  resume(): void;
  dispose(): void;
}
