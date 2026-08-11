"""Strict v1 behavior-preference payload parsing into typed runtime changes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from apps.assistant.src.modules.behavior_preferences import (
    ALLOWED_PATHS,
    BehaviorPreferenceChange,
)


CONTRACT_VERSION = "1.0"
ALLOWED_SCOPES = frozenset({"character", "user", "household"})
ALLOWED_ORIGINS = frozenset(
    {"llm_proposal", "user_interface", "administrator_interface"}
)
TOP_LEVEL_FIELDS = frozenset(
    {
        "contract_version",
        "proposal_id",
        "proposed_at",
        "scope",
        "scope_id",
        "origin",
        "status",
        "changes",
    }
)


@dataclass(frozen=True)
class BehaviorPreferenceProposal:
    proposal_id: str
    proposed_at: datetime
    scope: str
    scope_id: str
    origin: str
    changes: tuple[BehaviorPreferenceChange, ...]


def parse_behavior_preference_update(payload: object) -> BehaviorPreferenceProposal:
    if not isinstance(payload, dict) or set(payload) != TOP_LEVEL_FIELDS:
        raise ValueError("behavior preference payload fields are invalid")
    if payload["contract_version"] != CONTRACT_VERSION:
        raise ValueError("unsupported behavior preference contract version")
    proposal_id = _require_uuid(payload["proposal_id"])
    proposed_at = _require_datetime(payload["proposed_at"])
    scope = _require_choice(payload["scope"], ALLOWED_SCOPES, "scope")
    scope_id = _require_scope_id(payload["scope_id"])
    origin = _require_choice(payload["origin"], ALLOWED_ORIGINS, "origin")
    if payload["status"] != "proposed":
        raise ValueError("behavior preference status must be proposed")

    raw_changes = payload["changes"]
    if not isinstance(raw_changes, list) or not 1 <= len(raw_changes) <= 16:
        raise ValueError("behavior preference changes must contain 1 to 16 items")
    parsed: list[BehaviorPreferenceChange] = []
    seen: set[str] = set()
    for raw in raw_changes:
        if not isinstance(raw, dict) or set(raw) != {"path", "value"}:
            raise ValueError("behavior preference change fields are invalid")
        path = raw["path"]
        if not isinstance(path, str) or path not in ALLOWED_PATHS:
            raise ValueError("behavior preference change path is invalid")
        if path in seen:
            raise ValueError("behavior preference path may appear only once")
        seen.add(path)
        value = raw["value"]
        _validate_path_value(path, value)
        parsed.append(BehaviorPreferenceChange(path, value))

    return BehaviorPreferenceProposal(
        proposal_id=proposal_id,
        proposed_at=proposed_at,
        scope=scope,
        scope_id=scope_id,
        origin=origin,
        changes=tuple(parsed),
    )


def _validate_path_value(path: str, value: object) -> None:
    choices = {
        "character.humor": {"low", "moderate", "high"},
        "character.verbosity": {"concise", "normal", "detailed"},
        "character.formality": {"casual", "neutral", "formal"},
        "character.initiative": {"low", "moderate", "high"},
        "proactive.frequency": {"off", "low", "moderate"},
    }
    if path == "conversation.followup_timeout_sec":
        if not isinstance(value, int) or isinstance(value, bool) or not 5 <= value <= 120:
            raise ValueError("follow-up timeout value is invalid")
        return
    allowed = choices[path]
    if not isinstance(value, str) or value not in allowed:
        raise ValueError("behavior preference value is invalid")


def _require_uuid(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("proposal_id must be a UUID")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise ValueError("proposal_id must be a UUID") from error
    return str(parsed)


def _require_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("proposed_at must be a date-time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("proposed_at must be a date-time") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("proposed_at must include a timezone")
    return parsed


def _require_choice(value: object, allowed: frozenset[str], name: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"behavior preference {name} is invalid")
    return value


def _require_scope_id(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ValueError("behavior preference scope_id is invalid")
    return value
