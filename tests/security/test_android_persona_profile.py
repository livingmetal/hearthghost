from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONNECTION = (
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
    / "NodeConnection.java"
)


class AndroidPersonaProfileTests(unittest.TestCase):
    def test_native_transport_accepts_name_only_character_profile(self):
        source = CONNECTION.read_text(encoding="utf-8")
        self.assertIn('"character_profile"', source)
        self.assertIn('requireExactFields(profile, setOf("name"), true)', source)
        self.assertIn('new JSObject().put("name", name)', source)
        self.assertIn("MAX_CHARACTER_NAME_LENGTH = 80", source)
        self.assertIn("hasUnsupportedCharacterNameCodePoint", source)

    def test_profile_does_not_transport_persona_instructions_or_authority(self):
        source = CONNECTION.read_text(encoding="utf-8")
        profile_method = source.split(
            "private JSObject validatedCharacterProfileOutput", 1
        )[1].split("private boolean hasUnsupportedCharacterNameCodePoint", 1)[0]
        for forbidden in (
            "instructions",
            "system_prompt",
            "hard_policy",
            "capability",
            "assetUrl",
            "tool",
            "credential",
        ):
            self.assertNotIn(forbidden, profile_method)

    def test_native_name_validation_rejects_invisible_control_categories(self):
        source = CONNECTION.read_text(encoding="utf-8")
        for category in (
            "Character.CONTROL",
            "Character.FORMAT",
            "Character.SURROGATE",
            "Character.PRIVATE_USE",
            "Character.UNASSIGNED",
        ):
            self.assertIn(category, source)


if __name__ == "__main__":
    unittest.main()
