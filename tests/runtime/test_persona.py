from __future__ import annotations

import unittest

from apps.assistant.src.modules.orchestrator import SECURITY_INSTRUCTIONS, _compose_instructions
from apps.assistant.src.modules.persona import PersonaProfile


class PersonaTests(unittest.TestCase):
    def test_default_persona_is_conversational_and_low_initiative(self):
        persona = PersonaProfile()
        instructions = persona.conversation_instructions()

        self.assertIn("persistent character name is HearthGhost", instructions)
        self.assertIn("Humor level: moderate", instructions)
        self.assertIn("Conversational initiative: low", instructions)
        self.assertIn("never override security", instructions)

    def test_persona_preferences_do_not_replace_security_instructions(self):
        persona = PersonaProfile(
            name="Luna",
            humor="high",
            verbosity="concise",
            formality="casual",
            initiative="moderate",
        )

        instructions = _compose_instructions(persona)

        self.assertTrue(instructions.startswith(SECURITY_INSTRUCTIONS))
        self.assertIn("persistent character name is Luna", instructions)
        self.assertIn("Humor level: high", instructions)
        self.assertIn("Response verbosity: concise", instructions)
        self.assertIn("Never claim to execute devices", instructions)
        self.assertIn("every proposal remains pending Policy", instructions)

    def test_character_name_is_never_implied_to_be_the_user_name(self):
        for name in ("영희", "철수"):
            with self.subTest(name=name):
                instructions = PersonaProfile(name=name).conversation_instructions()

                self.assertIn(
                    f"You are {name}, the selected HearthGhost assistant character",
                    instructions,
                )
                self.assertIn(
                    f"The character name {name} identifies you, never the user",
                    instructions,
                )
                self.assertIn(
                    f"Do not call or address the user as {name}",
                    instructions,
                )
                self.assertIn("No human user name is provided", instructions)
                self.assertIn("Do not invent one", instructions)

    def test_schema_allowed_high_initiative_is_accepted(self):
        persona = PersonaProfile(initiative="high")
        self.assertEqual(persona.initiative, "high")

    def test_invalid_persona_preference_is_rejected(self):
        with self.assertRaises(ValueError):
            PersonaProfile(initiative="autonomous")
        with self.assertRaises(ValueError):
            PersonaProfile(humor="unbounded")
        with self.assertRaises(ValueError):
            PersonaProfile(verbosity="short")
        with self.assertRaises(ValueError):
            PersonaProfile(name="")


if __name__ == "__main__":
    unittest.main()
