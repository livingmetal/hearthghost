import { registerPlugin } from "@capacitor/core";

export interface VoiceOutputStatus {
  readonly initialized: boolean;
  readonly localVoiceAvailable: boolean;
  readonly mode: "embedded_only";
}

interface NativeVoiceOutputPlugin {
  status(options: { readonly locale: string }): Promise<VoiceOutputStatus>;
  speak(options: { readonly text: string; readonly locale: string }): Promise<{
    readonly utteranceId: string;
    readonly mode: "embedded_only";
    readonly voice: string;
  }>;
  stop(): Promise<void>;
}

const NativeVoiceOutput = registerPlugin<NativeVoiceOutputPlugin>("VoiceOutput");

export class AndroidVoiceOutput {
  status(locale = "ko-KR"): Promise<VoiceOutputStatus> {
    return NativeVoiceOutput.status({ locale });
  }

  async speak(text: string, locale = "ko-KR"): Promise<void> {
    const normalized = text.trim();
    if (normalized === "" || normalized.length > 8_000 || normalized.includes("\u0000")) {
      throw new Error("TTS text is invalid");
    }
    const result = await NativeVoiceOutput.speak({ text: normalized, locale });
    if (result.mode !== "embedded_only" || result.utteranceId.trim() === "") {
      throw new Error("Native TTS did not confirm embedded-only synthesis");
    }
  }

  stop(): Promise<void> {
    return NativeVoiceOutput.stop();
  }
}
