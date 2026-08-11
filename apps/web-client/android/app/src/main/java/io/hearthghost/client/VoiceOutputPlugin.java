package io.hearthghost.client;

import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.util.Comparator;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.regex.Pattern;

@CapacitorPlugin(name = "VoiceOutput")
public final class VoiceOutputPlugin extends Plugin {
    private static final int MAX_TEXT_LENGTH = 8_000;
    private static final Pattern LOCALE_PATTERN = Pattern.compile(
        "^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$"
    );

    private final AtomicBoolean initialized = new AtomicBoolean(false);
    private TextToSpeech textToSpeech;

    @Override
    public void load() {
        getBridge().executeOnMainThread(() -> {
            textToSpeech = new TextToSpeech(getContext(), status -> {
                initialized.set(status == TextToSpeech.SUCCESS);
                if (status == TextToSpeech.SUCCESS && textToSpeech != null) {
                    textToSpeech.setOnUtteranceProgressListener(new LocalUtteranceListener());
                }
            });
        });
    }

    @PluginMethod
    public void status(PluginCall call) {
        String locale = call.getString("locale", "ko-KR");
        if (!validLocale(locale)) {
            call.reject("tts_locale_invalid");
            return;
        }
        getBridge().executeOnMainThread(() -> {
            Voice localVoice = selectEmbeddedVoice(locale);
            call.resolve(
                new JSObject()
                    .put("initialized", initialized.get())
                    .put("localVoiceAvailable", localVoice != null)
                    .put("mode", "embedded_only")
            );
        });
    }

    @PluginMethod
    public void speak(PluginCall call) {
        String text = call.getString("text");
        String locale = call.getString("locale", "ko-KR");
        if (
            text == null
            || text.trim().isEmpty()
            || text.length() > MAX_TEXT_LENGTH
            || text.length() > TextToSpeech.getMaxSpeechInputLength()
            || text.indexOf('\0') >= 0
        ) {
            call.reject("tts_text_invalid");
            return;
        }
        if (!validLocale(locale)) {
            call.reject("tts_locale_invalid");
            return;
        }
        if (!getActivity().hasWindowFocus()) {
            call.reject("tts_foreground_required");
            return;
        }
        final String normalized = text.trim();
        getBridge().executeOnMainThread(() -> speakOnMainThread(call, normalized, locale));
    }

    @PluginMethod
    public void stop(PluginCall call) {
        getBridge().executeOnMainThread(() -> {
            if (textToSpeech != null) {
                textToSpeech.stop();
            }
            call.resolve();
        });
    }

    @Override
    protected void handleOnDestroy() {
        getBridge().executeOnMainThread(() -> {
            if (textToSpeech != null) {
                textToSpeech.stop();
                textToSpeech.shutdown();
                textToSpeech = null;
            }
            initialized.set(false);
        });
        super.handleOnDestroy();
    }

    private void speakOnMainThread(PluginCall call, String text, String locale) {
        if (!initialized.get() || textToSpeech == null) {
            call.reject("tts_not_initialized");
            return;
        }
        Voice voice = selectEmbeddedVoice(locale);
        if (voice == null || voice.isNetworkConnectionRequired()) {
            call.reject("embedded_tts_unavailable");
            return;
        }
        if (textToSpeech.setVoice(voice) != TextToSpeech.SUCCESS) {
            call.reject("embedded_tts_voice_rejected");
            return;
        }
        String utteranceId = UUID.randomUUID().toString();
        int queued = textToSpeech.speak(
            text,
            TextToSpeech.QUEUE_FLUSH,
            new Bundle(),
            utteranceId
        );
        if (queued != TextToSpeech.SUCCESS) {
            call.reject("embedded_tts_queue_failed");
            return;
        }
        call.resolve(
            new JSObject()
                .put("utteranceId", utteranceId)
                .put("mode", "embedded_only")
                .put("voice", voice.getName())
        );
    }

    private Voice selectEmbeddedVoice(String languageTag) {
        if (!initialized.get() || textToSpeech == null) {
            return null;
        }
        Locale requested = Locale.forLanguageTag(languageTag);
        if (requested.getLanguage().isEmpty()) {
            return null;
        }
        Set<Voice> voices = textToSpeech.getVoices();
        if (voices == null || voices.isEmpty()) {
            return null;
        }
        return voices.stream()
            .filter(voice -> !voice.isNetworkConnectionRequired())
            .filter(voice -> {
                Set<String> features = voice.getFeatures();
                return features == null
                    || !features.contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED);
            })
            .filter(voice -> voice.getLocale() != null)
            .filter(voice -> requested.getLanguage().equals(voice.getLocale().getLanguage()))
            .sorted(
                Comparator
                    .comparing((Voice voice) -> !requested.equals(voice.getLocale()))
                    .thenComparing(Comparator.comparingInt(Voice::getQuality).reversed())
                    .thenComparing(Voice::getName)
            )
            .findFirst()
            .orElse(null);
    }

    private static boolean validLocale(String locale) {
        return locale != null && LOCALE_PATTERN.matcher(locale).matches();
    }

    private final class LocalUtteranceListener extends UtteranceProgressListener {
        @Override
        public void onStart(String utteranceId) {
            notifyListeners("speechStart", new JSObject().put("utteranceId", utteranceId));
        }

        @Override
        public void onDone(String utteranceId) {
            notifyListeners("speechDone", new JSObject().put("utteranceId", utteranceId));
        }

        @Override
        public void onError(String utteranceId) {
            notifyListeners("speechError", new JSObject().put("utteranceId", utteranceId));
        }
    }
}
