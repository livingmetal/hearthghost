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

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.regex.Pattern;

@CapacitorPlugin(name = "VoiceOutput")
public final class VoiceOutputPlugin extends Plugin {
    private static final int MAX_TEXT_LENGTH = 8_000;
    private static final Pattern LOCALE_PATTERN = Pattern.compile(
        "^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$"
    );
    private static final Pattern UTTERANCE_ID_PATTERN = Pattern.compile("^[A-Za-z0-9._:-]{1,128}$");
    private static final String PROFILE_DEFAULT = "default";
    private static final String PROFILE_YOUNGHEE = "younghee";
    private static final String PROFILE_CHEOLSU = "cheolsu";

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
        String profile = call.getString("profile", PROFILE_DEFAULT);
        if (!validLocale(locale)) {
            call.reject("tts_locale_invalid");
            return;
        }
        if (!validProfile(profile)) {
            call.reject("tts_profile_invalid");
            return;
        }
        getBridge().executeOnMainThread(() -> {
            Voice localVoice = selectEmbeddedVoice(locale, profile);
            VoiceTuning tuning = tuningFor(profile);
            JSObject result = new JSObject()
                .put("initialized", initialized.get())
                .put("localVoiceAvailable", localVoice != null)
                .put("mode", "embedded_only")
                .put("profile", profile)
                .put("pitch", tuning.pitch)
                .put("rate", tuning.rate);
            if (localVoice != null) {
                result.put("voice", localVoice.getName());
            }
            call.resolve(result);
        });
    }

    @PluginMethod
    public void speak(PluginCall call) {
        String text = call.getString("text");
        String locale = call.getString("locale", "ko-KR");
        String profile = call.getString("profile", PROFILE_DEFAULT);
        String utteranceId = call.getString("utteranceId");
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
        if (!validProfile(profile)) {
            call.reject("tts_profile_invalid");
            return;
        }
        if (utteranceId == null || !UTTERANCE_ID_PATTERN.matcher(utteranceId).matches()) {
            call.reject("tts_utterance_id_invalid");
            return;
        }
        if (!getActivity().hasWindowFocus()) {
            call.reject("tts_foreground_required");
            return;
        }
        final String normalized = text.trim();
        getBridge().executeOnMainThread(
            () -> speakOnMainThread(call, normalized, locale, profile, utteranceId)
        );
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

    private void speakOnMainThread(
        PluginCall call,
        String text,
        String locale,
        String profile,
        String utteranceId
    ) {
        if (!initialized.get() || textToSpeech == null) {
            call.reject("tts_not_initialized");
            return;
        }
        Voice voice = selectEmbeddedVoice(locale, profile);
        if (voice == null || voice.isNetworkConnectionRequired()) {
            call.reject("embedded_tts_unavailable");
            return;
        }
        VoiceTuning tuning = tuningFor(profile);
        if (textToSpeech.setVoice(voice) != TextToSpeech.SUCCESS) {
            call.reject("embedded_tts_voice_rejected");
            return;
        }
        if (textToSpeech.setPitch(tuning.pitch) != TextToSpeech.SUCCESS) {
            call.reject("embedded_tts_pitch_rejected");
            return;
        }
        if (textToSpeech.setSpeechRate(tuning.rate) != TextToSpeech.SUCCESS) {
            call.reject("embedded_tts_rate_rejected");
            return;
        }
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
                .put("profile", profile)
                .put("pitch", tuning.pitch)
                .put("rate", tuning.rate)
        );
    }

    private Voice selectEmbeddedVoice(String languageTag, String profile) {
        List<Voice> candidates = embeddedVoices(languageTag);
        if (candidates.isEmpty()) {
            return null;
        }
        if (PROFILE_CHEOLSU.equals(profile) && candidates.size() > 1) {
            return candidates.get(1);
        }
        return candidates.get(0);
    }

    private List<Voice> embeddedVoices(String languageTag) {
        if (!initialized.get() || textToSpeech == null) {
            return List.of();
        }
        Locale requested = Locale.forLanguageTag(languageTag);
        if (requested.getLanguage().isEmpty()) {
            return List.of();
        }
        Set<Voice> voices = textToSpeech.getVoices();
        if (voices == null || voices.isEmpty()) {
            return List.of();
        }
        List<Voice> candidates = new ArrayList<>();
        for (Voice voice : voices) {
            if (voice.isNetworkConnectionRequired()) {
                continue;
            }
            Set<String> features = voice.getFeatures();
            if (
                features != null
                && features.contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED)
            ) {
                continue;
            }
            if (
                voice.getLocale() == null
                || !requested.getLanguage().equals(voice.getLocale().getLanguage())
            ) {
                continue;
            }
            candidates.add(voice);
        }
        candidates.sort(
            Comparator
                .comparing((Voice voice) -> !requested.equals(voice.getLocale()))
                .thenComparing(Comparator.comparingInt(Voice::getQuality).reversed())
                .thenComparing(Voice::getName)
        );
        return candidates;
    }

    private static VoiceTuning tuningFor(String profile) {
        if (PROFILE_YOUNGHEE.equals(profile)) {
            return new VoiceTuning(1.10f, 1.04f);
        }
        if (PROFILE_CHEOLSU.equals(profile)) {
            return new VoiceTuning(0.88f, 0.94f);
        }
        return new VoiceTuning(1.0f, 1.0f);
    }

    private static boolean validLocale(String locale) {
        return locale != null && LOCALE_PATTERN.matcher(locale).matches();
    }

    private static boolean validProfile(String profile) {
        return PROFILE_DEFAULT.equals(profile)
            || PROFILE_YOUNGHEE.equals(profile)
            || PROFILE_CHEOLSU.equals(profile);
    }

    private static final class VoiceTuning {
        private final float pitch;
        private final float rate;

        private VoiceTuning(float pitch, float rate) {
            this.pitch = pitch;
            this.rate = rate;
        }
    }

    private final class LocalUtteranceListener extends UtteranceProgressListener {
        @Override
        public void onStart(String utteranceId) {
            notifyListeners("speechStart", new JSObject().put("utteranceId", utteranceId));
        }

        @Override
        public void onRangeStart(String utteranceId, int start, int end, int frame) {
            notifyListeners(
                "speechRange",
                new JSObject()
                    .put("utteranceId", utteranceId)
                    .put("start", start)
                    .put("end", end)
            );
        }

        @Override
        public void onStop(String utteranceId, boolean interrupted) {
            notifyListeners("speechStop", new JSObject().put("utteranceId", utteranceId));
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
