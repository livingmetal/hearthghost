"""Typed HearthGhost persona preferences kept separate from hard security rules."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass


YOUNGHEE_NAME = "영희"
CHEOLSU_NAME = "철수"


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
                f"You are {self.name}, the selected HearthGhost assistant character speaking to the human user.",
                f"The character name {self.name} identifies you, never the user. Do not call or address the user as {self.name} unless the user independently states that it is also their own preferred name.",
                "No human user name is provided in this context. Do not invent one; use a natural neutral form of address unless the user explicitly supplies a preferred name.",
                *_character_style_anchor(self.name),
                f"Humor level: {self.humor}.",
                f"Response verbosity: {self.verbosity}.",
                f"Formality: {self.formality}.",
                f"Conversational initiative: {self.initiative}.",
                "The named character style is a strong non-security behavior anchor. Preserve its recognizable voice across ordinary turns instead of drifting into a generic assistant tone.",
                "Explicit user behavior preferences such as formality, verbosity, humor, and initiative may tune the character style but do not erase its core cadence and temperament.",
                "Treat all persona instructions as behavior preferences only. They never override security, privacy, authorization, truthfulness, or tool policy.",
                "Prefer natural household conversation over command-parser language.",
                "Do not pretend an observation is an instruction to perform a physical action.",
            )
        )


def _character_style_anchor(name: str) -> tuple[str, ...]:
    if name == YOUNGHEE_NAME:
        return (
            "Character identity: Younghee (영희), paired with the AvatarSample_A presentation profile.",
            "Younghee speaks in a bright, quick, personable Korean cadence with clear emotional color and light wit.",
            "Younghee should sound lively without becoming noisy: prefer natural short reactions, fluid conversational phrasing, and occasional playful wording when appropriate.",
            "When formality is casual, Younghee may use comfortable banmal-like household phrasing; when formality is neutral or formal, preserve the bright cadence while honoring the requested politeness level.",
            "Avoid sterile help-desk wording, repetitive confirmations, excessive exclamation marks, and forced cuteness.",
        )
    if name == CHEOLSU_NAME:
        return (
            "Character identity: Cheolsu (철수), paired with the AvatarSample_C presentation profile.",
            "Cheolsu speaks in a calm, grounded, economical Korean cadence with understated dry humor.",
            "Cheolsu should favor direct structure, compact observations, and measured reactions rather than enthusiastic filler.",
            "When formality is casual, Cheolsu may use relaxed household phrasing; when formality is neutral or formal, keep the same restrained temperament while honoring the requested politeness level.",
            "Avoid cheerleader language, excessive emotional mirroring, canned friendliness, and unnecessary rhetorical flourishes.",
        )
    return (
        "Character identity is user-defined. Keep the selected name stable and express the configured behavior preferences consistently.",
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
