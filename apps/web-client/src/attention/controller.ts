export type AttentionState = "sleeping" | "engaged";

export interface AttentionSnapshot {
  readonly state: AttentionState;
  readonly expiresAtMillis: number | null;
  readonly remainingMillis: number;
}

export interface AttentionClock {
  nowMillis(): number;
}

export class AttentionController {
  private state: AttentionState = "sleeping";
  private expiresAtMillis: number | null = null;

  constructor(
    private readonly timeoutMillis: number,
    private readonly clock: AttentionClock = { nowMillis: () => Date.now() },
  ) {
    if (!Number.isFinite(timeoutMillis) || timeoutMillis < 1_000 || timeoutMillis > 10 * 60_000) {
      throw new Error("Attention timeout must be between 1 second and 10 minutes");
    }
  }

  snapshot(): AttentionSnapshot {
    const now = this.clock.nowMillis();
    const remainingMillis = this.expiresAtMillis === null
      ? 0
      : Math.max(0, this.expiresAtMillis - now);
    return Object.freeze({
      state: this.state,
      expiresAtMillis: this.expiresAtMillis,
      remainingMillis,
    });
  }

  wakeByTouch(): AttentionSnapshot {
    this.state = "engaged";
    this.expiresAtMillis = this.clock.nowMillis() + this.timeoutMillis;
    return this.snapshot();
  }

  recordAddressedActivity(): AttentionSnapshot {
    if (this.state !== "engaged") {
      throw new Error("Addressed activity requires active attention");
    }
    this.expiresAtMillis = this.clock.nowMillis() + this.timeoutMillis;
    return this.snapshot();
  }

  expireIfIdle(): boolean {
    if (
      this.state === "engaged"
      && this.expiresAtMillis !== null
      && this.clock.nowMillis() >= this.expiresAtMillis
    ) {
      this.sleep();
      return true;
    }
    return false;
  }

  sleep(): AttentionSnapshot {
    this.state = "sleeping";
    this.expiresAtMillis = null;
    return this.snapshot();
  }

  canAcceptConversationInput(): boolean {
    this.expireIfIdle();
    return this.state === "engaged";
  }
}
