import { registerPlugin } from "@capacitor/core";

import type { HearthGhostCharacterId } from "../character/catalog.js";
import {
  dispatchSpeechDone,
  dispatchSpeechError,
  dispatchSpeechRange,
  dispatchSpeechStart,
} from "./speech-presentation.js";

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

interface ListenerHandle {
  remove(): Promise<void>;
}

interface SpeechEvent {
  readonly utteranceId: string;
}

interface SpeechRangeEvent extends SpeechEvent {
  readonly start: number;
  readonly end: number;
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
    readonly utteranceId: string;
  }): Promise<{
    readonly utteranceId: string;
    readonly mode: "embedded_only";
    readonly voice: string;
    readonly profile: VoiceProfileId;
    readonly pitch: number;
    readonly rate: number;
  }>;
  stop(): Promise<void>;
  addListener(eventName: "speechStart", listener: (event: SpeechEvent) => void): Promise<ListenerHandle>;
  addListener(eventName: "speechRange", listener: (event: SpeechRangeEvent) => void): Promise<ListenerHandle>;
  addListener(eventName: "speechDone", listener: (event: SpeechEvent) => void): Promise<ListenerHandle>;
  addListener(eventName: "speechStop", listener: (event: SpeechEvent) => void): Promise<ListenerHandle>;
  addListener(eventName: "speechError", listener: (event: SpeechEvent) => void): Promise<ListenerHandle>;
}

const NativeVoiceOutput = registerPlugin<NativeVoiceOutputPlugin>("VoiceOutput");

function createUtteranceId(): string {
  if (typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `hg-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export class AndroidVoiceOutput {
  private activeStopFallback: (() => void) | null = null;

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

    const utteranceId = createUtteranceId();
    let resolveCompletion: (() => void) | undefined;
    let rejectCompletion: ((error: Error) => void) | undefined;
    let terminalEventDispatched = false;
    const completion = new Promise<void>((resolve, reject) => {
      resolveCompletion = resolve;
      rejectCompletion = reject;
    });
    this.activeStopFallback = () => {
      if (!terminalEventDispatched) {
        terminalEventDispatched = true;
        dispatchSpeechDone({ utteranceId, text: normalized });
        resolveCompletion?.();
      }
    };

    const handles = await Promise.all([
      NativeVoiceOutput.addListener("speechStart", (event) => {
        if (event.utteranceId === utteranceId) {
          dispatchSpeechStart({ utteranceId, text: normalized });
        }
      }),
      NativeVoiceOutput.addListener("speechRange", (event) => {
        if (
          event.utteranceId === utteranceId
          && Number.isInteger(event.start)
          && Number.isInteger(event.end)
          && event.start >= 0
          && event.end >= event.start
          && event.end <= normalized.length
        ) {
          dispatchSpeechRange({
            utteranceId,
            text: normalized,
            start: event.start,
            end: event.end,
          });
        }
      }),
      NativeVoiceOutput.addListener("speechDone", (event) => {
        if (event.utteranceId === utteranceId && !terminalEventDispatched) {
          terminalEventDispatched = true;
          dispatchSpeechDone({ utteranceId, text: normalized });
          resolveCompletion?.();
        }
      }),
      NativeVoiceOutput.addListener("speechStop", (event) => {
        if (event.utteranceId === utteranceId && !terminalEventDispatched) {
          terminalEventDispatched = true;
          dispatchSpeechDone({ utteranceId, text: normalized });
          resolveCompletion?.();
        }
      }),
      NativeVoiceOutput.addListener("speechError", (event) => {
        if (event.utteranceId === utteranceId && !terminalEventDispatched) {
          terminalEventDispatched = true;
          dispatchSpeechError({ utteranceId, text: normalized });
          rejectCompletion?.(new Error("Native TTS playback failed"));
        }
      }),
    ]);

    try {
      const result = await NativeVoiceOutput.speak({
        text: normalized,
        locale,
        profile,
        utteranceId,
      });
      if (
        result.mode !== "embedded_only"
        || result.utteranceId !== utteranceId
        || result.profile !== profile
      ) {
        throw new Error("Native TTS did not confirm the requested embedded-only character voice");
      }
      await completion;
    } catch (error) {
      if (!terminalEventDispatched) {
        dispatchSpeechError({ utteranceId, text: normalized });
      }
      throw error;
    } finally {
      if (this.activeStopFallback !== null) {
        this.activeStopFallback = null;
      }
      await Promise.all(handles.map(async (handle) => handle.remove().catch(() => undefined)));
    }
  }

  async stop(): Promise<void> {
    try {
      await NativeVoiceOutput.stop();
    } finally {
      this.activeStopFallback?.();
    }
  }
}
