package io.hearthghost.client;

import android.Manifest;
import android.annotation.TargetApi;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;

import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

import java.util.ArrayList;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.regex.Pattern;

@CapacitorPlugin(
    name = "VoiceInput",
    permissions = {
        @Permission(alias = "microphone", strings = { Manifest.permission.RECORD_AUDIO })
    }
)
public final class VoiceInputPlugin extends Plugin {
    private static final long TOUCH_GATE_MILLIS = 2_000L;
    private static final int MAX_TRANSCRIPT_LENGTH = 4_000;
    private static final Pattern LOCALE_PATTERN = Pattern.compile(
        "^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$"
    );

    private final AtomicBoolean listening = new AtomicBoolean(false);
    private SpeechRecognizer recognizer;

    @PluginMethod
    public void status(PluginCall call) {
        call.resolve(statusOutput());
    }

    @PluginMethod
    public void requestMicrophonePermission(PluginCall call) {
        if (!recentForegroundTouch()) {
            call.reject("voice_touch_gate_required");
            return;
        }
        if (getPermissionState("microphone") == PermissionState.GRANTED) {
            call.resolve(statusOutput());
            return;
        }
        requestPermissionForAlias("microphone", call, "microphonePermissionCallback");
    }

    @PermissionCallback
    private void microphonePermissionCallback(PluginCall call) {
        if (getPermissionState("microphone") != PermissionState.GRANTED) {
            call.reject("microphone_permission_denied");
            return;
        }
        call.resolve(statusOutput());
    }

    @PluginMethod
    public void startOnDeviceRecognition(PluginCall call) {
        String locale = call.getString("locale", "ko-KR");
        if (locale == null || !LOCALE_PATTERN.matcher(locale).matches()) {
            call.reject("voice_locale_invalid");
            return;
        }
        if (getPermissionState("microphone") != PermissionState.GRANTED) {
            call.reject("microphone_permission_required");
            return;
        }
        if (!recentForegroundTouch()) {
            call.reject("voice_touch_gate_required");
            return;
        }
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) {
            call.reject("on_device_speech_requires_android_12");
            return;
        }
        if (!SpeechRecognizer.isOnDeviceRecognitionAvailable(getContext())) {
            call.reject("on_device_speech_unavailable");
            return;
        }
        if (!listening.compareAndSet(false, true)) {
            call.reject("voice_recognition_in_progress");
            return;
        }
        final String selectedLocale = locale;
        getBridge().executeOnMainThread(() -> startOnMainThread(selectedLocale));
        call.resolve(new JSObject().put("listening", true).put("mode", "on_device_only"));
    }

    @PluginMethod
    public void cancelRecognition(PluginCall call) {
        getBridge().executeOnMainThread(() -> finishRecognition(true));
        call.resolve();
    }

    @Override
    protected void handleOnDestroy() {
        getBridge().executeOnMainThread(() -> finishRecognition(true));
        super.handleOnDestroy();
    }

    @TargetApi(Build.VERSION_CODES.S)
    private void startOnMainThread(String locale) {
        try {
            recognizer = SpeechRecognizer.createOnDeviceSpeechRecognizer(getContext());
            recognizer.setRecognitionListener(new LocalRecognitionListener());
            Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            intent.putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
            );
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, locale);
            intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
            intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false);
            recognizer.startListening(intent);
        } catch (RuntimeException error) {
            notifyVoiceError("on_device_speech_start_failed");
            finishRecognition(false);
        }
    }

    private boolean recentForegroundTouch() {
        if (!(getActivity() instanceof MainActivity)) {
            return false;
        }
        MainActivity activity = (MainActivity) getActivity();
        return activity.hasWindowFocus() && activity.hasRecentUserInteraction(TOUCH_GATE_MILLIS);
    }

    private JSObject statusOutput() {
        boolean onDeviceAvailable = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
            && SpeechRecognizer.isOnDeviceRecognitionAvailable(getContext());
        return new JSObject()
            .put("permission", getPermissionState("microphone").toString().toLowerCase(Locale.ROOT))
            .put("onDeviceAvailable", onDeviceAvailable)
            .put("listening", listening.get())
            .put("mode", "on_device_only");
    }

    private void notifyVoiceError(String reason) {
        notifyListeners("voiceError", new JSObject().put("reason", reason));
    }

    private void finishRecognition(boolean cancel) {
        SpeechRecognizer current = recognizer;
        recognizer = null;
        if (current != null) {
            try {
                if (cancel) {
                    current.cancel();
                }
            } catch (RuntimeException ignored) {
                // Destroy below remains mandatory even if cancel fails.
            }
            current.destroy();
        }
        listening.set(false);
    }

    private final class LocalRecognitionListener implements RecognitionListener {
        @Override
        public void onReadyForSpeech(Bundle params) {}

        @Override
        public void onBeginningOfSpeech() {}

        @Override
        public void onRmsChanged(float rmsdB) {}

        @Override
        public void onBufferReceived(byte[] buffer) {
            // Raw microphone bytes are deliberately ignored and never bridged to JavaScript.
        }

        @Override
        public void onEndOfSpeech() {}

        @Override
        public void onError(int error) {
            notifyListeners("voiceError", new JSObject().put("reason", "recognition_error").put("code", error));
            finishRecognition(false);
        }

        @Override
        public void onResults(Bundle results) {
            ArrayList<String> candidates = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
            if (candidates == null || candidates.isEmpty()) {
                notifyVoiceError("recognition_empty");
                finishRecognition(false);
                return;
            }
            String transcript = candidates.get(0) == null ? "" : candidates.get(0).trim();
            if (transcript.isEmpty() || transcript.length() > MAX_TRANSCRIPT_LENGTH || transcript.indexOf('\0') >= 0) {
                notifyVoiceError("recognition_result_invalid");
                finishRecognition(false);
                return;
            }
            JSObject output = new JSObject()
                .put("text", transcript)
                .put("source", "on_device_stt");
            float[] confidence = results.getFloatArray(SpeechRecognizer.CONFIDENCE_SCORES);
            if (confidence != null && confidence.length > 0 && confidence[0] >= 0.0f && confidence[0] <= 1.0f) {
                output.put("confidence", confidence[0]);
            }
            notifyListeners("voiceResult", output);
            finishRecognition(false);
        }

        @Override
        public void onPartialResults(Bundle partialResults) {
            // Partial text is not exposed to reduce accidental pre-final data handling.
        }

        @Override
        public void onEvent(int eventType, Bundle params) {}
    }
}
