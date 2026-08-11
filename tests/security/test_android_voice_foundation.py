from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT
    / "apps"
    / "web-client"
    / "android"
    / "app"
    / "src"
    / "main"
    / "java"
    / "io"
    / "hearthghost"
    / "client"
)


class AndroidVoiceFoundationTests(unittest.TestCase):
    def test_voice_uses_on_device_recognizer_only(self):
        voice = (SOURCE / "VoiceInputPlugin.java").read_text(encoding="utf-8")

        self.assertIn("SpeechRecognizer.createOnDeviceSpeechRecognizer", voice)
        self.assertIn("SpeechRecognizer.isOnDeviceRecognitionAvailable", voice)
        self.assertNotIn("SpeechRecognizer.createSpeechRecognizer(", voice)
        self.assertNotIn("EXTRA_PREFER_OFFLINE", voice)
        self.assertIn("Build.VERSION.SDK_INT < Build.VERSION_CODES.S", voice)
        self.assertIn('mode", "on_device_only"', voice)

    def test_microphone_start_requires_permission_foreground_and_recent_touch(self):
        voice = (SOURCE / "VoiceInputPlugin.java").read_text(encoding="utf-8")
        activity = (SOURCE / "MainActivity.java").read_text(encoding="utf-8")

        self.assertIn('@Permission(alias = "microphone"', voice)
        self.assertIn('getPermissionState("microphone")', voice)
        self.assertIn("recentForegroundTouch()", voice)
        self.assertIn("activity.hasWindowFocus()", voice)
        self.assertIn("activity.hasRecentUserInteraction(TOUCH_GATE_MILLIS)", voice)
        self.assertIn("onUserInteraction()", activity)
        self.assertIn("SystemClock.elapsedRealtime()", activity)

    def test_raw_audio_and_partial_results_are_not_bridged(self):
        voice = (SOURCE / "VoiceInputPlugin.java").read_text(encoding="utf-8")

        buffer_method = voice.split("public void onBufferReceived(byte[] buffer)", 1)[1].split(
            "@Override", 1
        )[0]
        partial_method = voice.split("public void onPartialResults(Bundle partialResults)", 1)[1].split(
            "@Override", 1
        )[0]
        self.assertNotIn("notifyListeners", buffer_method)
        self.assertNotIn("notifyListeners", partial_method)
        self.assertIn('notifyListeners("voiceResult"', voice)
        self.assertIn('source", "on_device_stt"', voice)

    def test_voice_plugin_has_no_provider_or_network_credentials(self):
        voice = (SOURCE / "VoiceInputPlugin.java").read_text(encoding="utf-8")
        for forbidden in (
            "OPENAI_API_KEY",
            "Authorization",
            "Bearer ",
            "HttpURLConnection",
            "OkHttpClient",
            "Socket(",
        ):
            self.assertNotIn(forbidden, voice)


if __name__ == "__main__":
    unittest.main()
