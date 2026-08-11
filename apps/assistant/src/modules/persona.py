"""Typed HearthGhost persona preferences kept separate from hard security rules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PersonaProfile:
    name: str = "HearthGhost"
    humor: str = "moderate"
    verbosity: str = "normal"
    formality: str = "casual"
    initiative: str = "low"

    def __post_init__(self) -> None:
        if not self.name.strip() or len(self.name) > 80:
            raise ValueError("persona name must contain 1 to 80 characters")
        _require_choice("humor", self.humor, {"low", "moderate", "high"})
        _require_choice("verbosity", self.verbosity, {"short", "normal", "detailed"})
        _require_choice("formality", self.formality, {"casual", "neutral", "formal"})
        _require_choice("initiative", self.initiative, {"low", "moderate"})

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


def _require_choice(name: str, value: str, allowed: set[str]) -> None:
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of: {choices}")
