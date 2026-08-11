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
            verbosity="short",
            formality="casual",
            initiative="moderate",
        )

        instructions = _compose_instructions(persona)

        self.assertTrue(instructions.startswith(SECURITY_INSTRUCTIONS))
        self.assertIn("persistent character name is Luna", instructions)
        self.assertIn("Humor level: high", instructions)
        self.assertIn("Never claim to execute devices", instructions)
        self.assertIn("every proposal remains pending Policy", instructions)

    def test_invalid_persona_preference_is_rejected(self):
        with self.assertRaises(ValueError):
            PersonaProfile(initiative="autonomous")
        with self.assertRaises(ValueError):
            PersonaProfile(humor="unbounded")
        with self.assertRaises(ValueError):
            PersonaProfile(name="")


if __name__ == "__main__":
    unittest.main()
