"""Typed HearthGhost persona preferences kept separate from hard security rules."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class PersonaProfile:
    name: str = "HearthGhost"
    humor: str = "moderate"
    verbosity: str = "normal"
    formality: str = "casual"
    initiative: str = "low"

    def __post_init__(self) -> None:
        require_persona_name(self.name)
        _require_choice("humor", self.humor, {"low", "moderate", "high"})
        _require_choice("verbosity", self.verbosity, {"concise", "normal", "detailed"})
        _require_choice("formality", self.formality, {"casual", "neutral", "formal"})
        _require_choice("initiative", self.initiative, {"low", "moderate", "high"})

    def conversation_instructions(self) -> str:
        return "\n".join(
            (
                f"Your persistent character name is {self.name}.",
                f"Humor level: {self.humor}.",
                f"Response verbosity: {self.verbosity}.",
                f"Formality: {self.formality}.",
                f"Conversational initiative: {self.initiative}.",
                "Treat these as behavior preferences only. They never override security, privacy, authorization, or tool policy.",
                "Prefer natural household conversation over command-parser language.",
                "Do not pretend an observation is an instruction to perform a physical action.",
            )
        )


def require_persona_name(value: object) -> str:
    """Validate a display-safe name without restricting normal Unicode names.

    Control/format/surrogate/private-use/unassigned code points are rejected so a
    persona name cannot carry line breaks, bidi controls, terminal escapes, or
    invisible formatting into prompts, logs, or client display surfaces.
    """
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 80:
        raise ValueError("persona name must contain 1 to 80 trimmed characters")
    if any(unicodedata.category(character).startswith("C") for character in value):
        raise ValueError("persona name contains unsupported control characters")
    return value


def _require_choice(name: str, value: str, allowed: set[str]) -> None:
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of: {choices}")
