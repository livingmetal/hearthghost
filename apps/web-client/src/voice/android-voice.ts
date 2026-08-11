import { registerPlugin } from "@capacitor/core";

export interface VoiceInputStatus {
  readonly permission: string;
  readonly onDeviceAvailable: boolean;
  readonly listening: boolean;
  readonly mode: "on_device_only";
}

export interface VoiceTranscriptResult {
  readonly text: string;
  readonly source: "on_device_stt";
  readonly confidence?: number;
}

export interface VoiceErrorResult {
  readonly reason: string;
  readonly code?: number;
}

interface ListenerHandle {
  remove(): Promise<void>;
}

interface NativeVoiceInputPlugin {
  status(): Promise<VoiceInputStatus>;
  requestMicrophonePermission(): Promise<VoiceInputStatus>;
  startOnDeviceRecognition(options: { readonly locale: string }): Promise<{
    readonly listening: boolean;
    readonly mode: "on_device_only";
  }>;
  cancelRecognition(): Promise<void>;
  addListener(
    eventName: "voiceResult",
    listener: (event: VoiceTranscriptResult) => void,
  ): Promise<ListenerHandle>;
  addListener(
    eventName: "voiceError",
    listener: (event: VoiceErrorResult) => void,
  ): Promise<ListenerHandle>;
}

const NativeVoiceInput = registerPlugin<NativeVoiceInputPlugin>("VoiceInput");

export class AndroidVoiceInput {
  status(): Promise<VoiceInputStatus> {
    return NativeVoiceInput.status();
  }

  requestMicrophonePermission(): Promise<VoiceInputStatus> {
    return NativeVoiceInput.requestMicrophonePermission();
  }

  async start(locale = "ko-KR"): Promise<void> {
    const result = await NativeVoiceInput.startOnDeviceRecognition({ locale });
    if (!result.listening || result.mode !== "on_device_only") {
      throw new Error("Native voice input did not enter on-device listening mode");
    }
  }

  cancel(): Promise<void> {
    return NativeVoiceInput.cancelRecognition();
  }

  onTranscript(listener: (event: VoiceTranscriptResult) => void): Promise<ListenerHandle> {
    return NativeVoiceInput.addListener("voiceResult", listener);
  }

  onError(listener: (event: VoiceErrorResult) => void): Promise<ListenerHandle> {
    return NativeVoiceInput.addListener("voiceError", listener);
  }
}
