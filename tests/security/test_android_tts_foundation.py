from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANDROID = ROOT / "apps" / "web-client" / "android" / "app" / "src" / "main"
SOURCE = ANDROID / "java" / "io" / "hearthghost" / "client"
ANDROID_NAMESPACE = "{http://schemas.android.com/apk/res/android}"


class AndroidTtsFoundationTests(unittest.TestCase):
    def test_tts_selects_embedded_voice_only(self):
        source = (SOURCE / "VoiceOutputPlugin.java").read_text(encoding="utf-8")

        self.assertIn("voice.isNetworkConnectionRequired()", source)
        self.assertIn("TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED", source)
        self.assertIn("textToSpeech.setVoice(voice)", source)
        self.assertIn('mode", "embedded_only"', source)
        self.assertNotIn("synthesizeToFile", source)
        self.assertNotIn("KEY_FEATURE_NETWORK_SYNTHESIS", source)

    def test_tts_character_profiles_are_local_and_distinct(self):
        source = (SOURCE / "VoiceOutputPlugin.java").read_text(encoding="utf-8")

        self.assertIn('PROFILE_YOUNGHEE = "younghee"', source)
        self.assertIn('PROFILE_CHEOLSU = "cheolsu"', source)
        self.assertIn("new VoiceTuning(1.10f, 1.04f)", source)
        self.assertIn("new VoiceTuning(0.88f, 0.94f)", source)
        self.assertIn("candidates.size() > 1", source)
        self.assertIn("candidates.get(1)", source)
        self.assertIn("textToSpeech.setPitch", source)
        self.assertIn("textToSpeech.setSpeechRate", source)

    def test_tts_has_no_network_or_provider_client(self):
        source = (SOURCE / "VoiceOutputPlugin.java").read_text(encoding="utf-8")
        for forbidden in (
            "OPENAI_API_KEY",
            "Authorization",
            "Bearer ",
            "HttpURLConnection",
            "OkHttpClient",
            "Socket(",
        ):
            self.assertNotIn(forbidden, source)

    def test_manifest_declares_tts_service_visibility_without_tts_specific_network_permission(self):
        manifest = ET.parse(ANDROID / "AndroidManifest.xml").getroot()
        actions = {
            item.attrib.get(f"{ANDROID_NAMESPACE}name")
            for queries in manifest.findall("queries")
            for intent in queries.findall("intent")
            for item in intent.findall("action")
        }
        self.assertIn("android.intent.action.TTS_SERVICE", actions)

        permissions = {
            item.attrib[f"{ANDROID_NAMESPACE}name"]
            for item in manifest.findall("uses-permission")
        }
        self.assertEqual(
            permissions,
            {
                "android.permission.INTERNET",
                "android.permission.RECORD_AUDIO",
                "android.permission.POST_NOTIFICATIONS",
                "android.permission.RECEIVE_BOOT_COMPLETED",
            },
        )
        self.assertNotIn("android.permission.SCHEDULE_EXACT_ALARM", permissions)
        self.assertNotIn("android.permission.USE_EXACT_ALARM", permissions)


if __name__ == "__main__":
    unittest.main()
