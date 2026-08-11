import { registerPlugin } from "@capacitor/core";

import type { HearthGhostCharacterId } from "../character/catalog.js";

export type VoiceProfileId = HearthGhostCharacterId | "default";

export interface VoiceOutputStatus {
  readonly initialized: boolean;
  readonly localVoiceAvailable: boolean;
  readonly mode: "embedded_only";
  readonly profile?: VoiceProfileId;
  readonly voice?: string;
  readonly pitch?: number;
  readonly rate?: number;
}

interface NativeVoiceOutputPlugin {
  status(options: {
    readonly locale: string;
    readonly profile: VoiceProfileId;
  }): Promise<VoiceOutputStatus>;
  speak(options: {
    readonly text: string;
    readonly locale: string;
    readonly profile: VoiceProfileId;
  }): Promise<{
    readonly utteranceId: string;
    readonly mode: "embedded_only";
    readonly voice: string;
    readonly profile: VoiceProfileId;
    readonly pitch: number;
    readonly rate: number;
  }>;
  stop(): Promise<void>;
}

const NativeVoiceOutput = registerPlugin<NativeVoiceOutputPlugin>("VoiceOutput");

export class AndroidVoiceOutput {
  status(locale = "ko-KR", profile: VoiceProfileId = "default"): Promise<VoiceOutputStatus> {
    return NativeVoiceOutput.status({ locale, profile });
  }

  async speak(
    text: string,
    locale = "ko-KR",
    profile: VoiceProfileId = "default",
  ): Promise<void> {
    const normalized = text.trim();
    if (normalized === "" || normalized.length > 8_000 || normalized.includes("\u0000")) {
      throw new Error("TTS text is invalid");
    }
    const result = await NativeVoiceOutput.speak({
      text: normalized,
      locale,
      profile,
    });
    if (
      result.mode !== "embedded_only"
      || result.utteranceId.trim() === ""
      || result.profile !== profile
    ) {
      throw new Error("Native TTS did not confirm the requested embedded-only character voice");
    }
  }

  stop(): Promise<void> {
    return NativeVoiceOutput.stop();
  }
}
