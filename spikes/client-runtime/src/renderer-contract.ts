export type CharacterState =
  | "sleeping"
  | "listening"
  | "thinking"
  | "speaking"
  | "engaged";

export type CharacterEmotion =
  | "neutral"
  | "happy"
  | "amused"
  | "curious"
  | "concerned"
  | "surprised";

export interface CharacterRenderer {
  mount(viewport: HTMLElement): Promise<void>;
  resize(width: number, height: number, pixelRatio: number): void;
  render(state: CharacterState, emotion: CharacterEmotion): void;
  suspend(): void;
  resume(): void;
  dispose(): void;
}
