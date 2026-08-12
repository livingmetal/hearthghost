"""Reviewed Tool definitions and untrusted proposal domain objects.

Tool proposals remain inert data. Registry entries are server-owned reviewed
metadata and never carry executable callables or provider credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re
from types import MappingProxyType
from typing import Mapping
from uuid import UUID, uuid4

from apps.assistant.src.ports.llm import ProposedAction


_TOOL_NAME = re.compile(r"[a-z][a-z0-9_-]{0,63}(\.[a-z][a-z0-9_-]{0,63})+")
_CAPABILITY = re.compile(r"[a-z][a-z0-9_-]{0,63}(?:\.[a-z][a-z0-9_-]{0,63})*")
_DEVICE_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
_SCHEMA_TOP_KEYS = frozenset(
    {"type", "properties", "required", "additionalProperties", "minProperties", "maxProperties"}
)
_SCHEMA_PROPERTY_KEYS = frozenset(
    {"type", "enum", "minLength", "maxLength", "minimum", "maximum", "pattern"}
)


class ToolEffect(str, Enum):
    INFORMATIONAL = "informational"
    EXTERNAL_READ = "external_read"
    EXTERNAL_WRITE = "external_write"
    PHYSICAL_ACTION = "physical_action"


class ToolRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolRequiredContext(str, Enum):
    NONE = "none"
    ACTIVE_SESSION = "active_session"
    EXPLICIT_USER_REQUEST = "explicit_user_request"
    ADMINISTRATOR_ACTION = "administrator_action"


class ActorRole(str, Enum):
    ADMINISTRATOR = "administrator"
    HOUSEHOLD_MEMBER = "household_member"
    GUEST = "guest"


class ConfirmationPolicy(str, Enum):
    NONE = "none"
    CONTEXTUAL = "contextual"
    EXPLICIT = "explicit"


class AuditLevel(str, Enum):
    NONE = "none"
    METADATA = "metadata"
    SECURITY = "security"


class ToolProposerType(str, Enum):
    LLM = "llm"
    USER_INTERFACE = "user_interface"
    SYSTEM = "system"


def _validate_identifier(value: object, *, field: str, maximum: int = 128) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValueError(f"{field} must be a non-empty bounded string")
    return value


def _freeze_json(value: object, *, depth: int = 0) -> object:
    if depth > 8:
        raise ValueError("tool JSON data exceeds the supported nesting depth")
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Mapping):
        if len(value) > 64:
            raise ValueError("tool JSON object contains too many keys")
        frozen: dict[str, object] = {}
        for key, child in value.items():
            if not isinstance(key, str) or not key or len(key) > 128:
                raise ValueError("tool JSON object has an invalid key")
            frozen[key] = _freeze_json(child, depth=depth + 1)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        if len(value) > 64:
            raise ValueError("tool JSON array contains too many values")
        return tuple(_freeze_json(child, depth=depth + 1) for child in value)
    raise ValueError("tool data must contain JSON-compatible values only")


def _validate_schema(schema: Mapping[str, object]) -> None:
    unsupported = set(schema) - _SCHEMA_TOP_KEYS
    if unsupported:
        raise ValueError(f"unsupported tool argument schema keyword: {sorted(unsupported)[0]}")
    if schema.get("type") != "object":
        raise ValueError("tool argument schema must declare type=object")
    if schema.get("additionalProperties") is not False:
        raise ValueError("tool argument schema must deny additionalProperties")
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        raise ValueError("tool argument schema requires a properties object")
    required = schema.get("required", ())
    if not isinstance(required, (list, tuple)) or any(not isinstance(item, str) for item in required):
        raise ValueError("tool argument schema required must be a string array")
    if len(set(required)) != len(required) or not set(required).issubset(properties):
        raise ValueError("tool argument schema required fields must be unique known properties")
    for numeric_key in ("minProperties", "maxProperties"):
        if numeric_key in schema:
            value = schema[numeric_key]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{numeric_key} must be a non-negative integer")
    if (
        "minProperties" in schema
        and "maxProperties" in schema
        and int(schema["minProperties"]) > int(schema["maxProperties"])
    ):
        raise ValueError("minProperties cannot exceed maxProperties")
    for name, rule in properties.items():
        if not isinstance(name, str) or not name or len(name) > 128 or not isinstance(rule, Mapping):
            raise ValueError("tool argument schema contains an invalid property")
        unsupported_rule = set(rule) - _SCHEMA_PROPERTY_KEYS
        if unsupported_rule:
            raise ValueError(
                f"unsupported tool property schema keyword: {sorted(unsupported_rule)[0]}"
            )
        declared_type = rule.get("type")
        if declared_type is not None and declared_type not in {"string", "integer", "number", "boolean"}:
            raise ValueError("unsupported tool property type")
        enum = rule.get("enum")
        if enum is not None:
            if not isinstance(enum, (list, tuple)) or not enum:
                raise ValueError("tool property enum must be a non-empty array")
            for candidate in enum:
                _freeze_json(candidate)
        if "pattern" in rule:
            pattern = rule["pattern"]
            if not isinstance(pattern, str) or len(pattern) > 256:
                raise ValueError("tool property pattern is invalid")
            re.compile(pattern)
        for key in ("minLength", "maxLength"):
            if key in rule:
                value = rule[key]
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    raise ValueError(f"tool property {key} must be a non-negative integer")
        for key in ("minimum", "maximum"):
            if key in rule:
                value = rule[key]
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    raise ValueError(f"tool property {key} must be numeric")


def _matches_property_rule(value: object, rule: Mapping[str, object]) -> bool:
    declared_type = rule.get("type")
    if declared_type == "string" and not isinstance(value, str):
        return False
    if declared_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        return False
    if declared_type == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        return False
    if declared_type == "boolean" and not isinstance(value, bool):
        return False
    enum = rule.get("enum")
    if isinstance(enum, (list, tuple)) and value not in enum:
        return False
    if isinstance(value, str):
        minimum = rule.get("minLength")
        maximum = rule.get("maxLength")
        pattern = rule.get("pattern")
        if isinstance(minimum, int) and len(value) < minimum:
            return False
        if isinstance(maximum, int) and len(value) > maximum:
            return False
        if isinstance(pattern, str) and re.fullmatch(pattern, value) is None:
            return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum_number = rule.get("minimum")
        maximum_number = rule.get("maximum")
        if isinstance(minimum_number, (int, float)) and value < minimum_number:
            return False
        if isinstance(maximum_number, (int, float)) and value > maximum_number:
            return False
    return True


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    effect: ToolEffect
    risk_level: ToolRiskLevel
    required_context: ToolRequiredContext
    required_roles: frozenset[ActorRole]
    confirmation_policy: ConfirmationPolicy
    audit_level: AuditLevel
    arguments_schema: Mapping[str, object]
    allowed_capabilities: frozenset[str] = frozenset()
    allowed_devices: frozenset[str] = frozenset()
    contract_version: str = "1.0"

    def __post_init__(self) -> None:
        if self.contract_version != "1.0" or _TOOL_NAME.fullmatch(self.name) is None:
            raise ValueError("tool definition identity is invalid")
        if not isinstance(self.description, str) or not self.description or len(self.description) > 512:
            raise ValueError("tool description is invalid")
        if not self.required_roles or not all(isinstance(role, ActorRole) for role in self.required_roles):
            raise ValueError("tool definition requires at least one valid role")
        if any(_CAPABILITY.fullmatch(value) is None for value in self.allowed_capabilities):
            raise ValueError("tool definition contains an invalid capability")
        if any(_DEVICE_ID.fullmatch(value) is None for value in self.allowed_devices):
            raise ValueError("tool definition contains an invalid device id")
        if self.effect is ToolEffect.PHYSICAL_ACTION:
            if self.confirmation_policy is ConfirmationPolicy.NONE:
                raise ValueError("physical actions require confirmation")
            if self.audit_level is AuditLevel.NONE:
                raise ValueError("physical actions require audit metadata")
        if self.risk_level is ToolRiskLevel.CRITICAL:
            if self.confirmation_policy is not ConfirmationPolicy.EXPLICIT:
                raise ValueError("critical tools require explicit confirmation")
            if self.audit_level is not AuditLevel.SECURITY:
                raise ValueError("critical tools require security audit")
        if not isinstance(self.arguments_schema, Mapping):
            raise ValueError("tool arguments_schema must be an object")
        _validate_schema(self.arguments_schema)
        object.__setattr__(self, "arguments_schema", _freeze_json(self.arguments_schema))
        object.__setattr__(self, "required_roles", frozenset(self.required_roles))
        object.__setattr__(self, "allowed_capabilities", frozenset(self.allowed_capabilities))
        object.__setattr__(self, "allowed_devices", frozenset(self.allowed_devices))

    def arguments_are_valid(self, arguments: Mapping[str, object]) -> bool:
        if not isinstance(arguments, Mapping):
            return False
        schema = self.arguments_schema
        properties = schema.get("properties")
        required = schema.get("required", ())
        if not isinstance(properties, Mapping) or not isinstance(required, tuple):
            return False
        keys = set(arguments)
        if not set(required).issubset(keys) or not keys.issubset(properties):
            return False
        minimum = schema.get("minProperties")
        maximum = schema.get("maxProperties")
        if isinstance(minimum, int) and len(arguments) < minimum:
            return False
        if isinstance(maximum, int) and len(arguments) > maximum:
            return False
        for name, value in arguments.items():
            rule = properties.get(name)
            if not isinstance(rule, Mapping) or not _matches_property_rule(value, rule):
                return False
        return True


@dataclass(frozen=True)
class ToolProposer:
    type: ToolProposerType
    id: str

    def __post_init__(self) -> None:
        _validate_identifier(self.id, field="proposer id")


@dataclass(frozen=True)
class ToolProposalContext:
    request_id: str
    explicit_user_request: bool
    session_id: str | None = None
    node_id: str | None = None
    actor_id: str | None = None
    confirmation_id: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier(self.request_id, field="request id")
        if not isinstance(self.explicit_user_request, bool):
            raise ValueError("explicit_user_request must be boolean")
        for field_name in ("session_id", "actor_id", "confirmation_id"):
            value = getattr(self, field_name)
            if value is not None:
                _validate_identifier(value, field=field_name.replace("_", " "))
        if self.node_id is not None and _DEVICE_ID.fullmatch(self.node_id) is None:
            raise ValueError("node id is invalid")


@dataclass(frozen=True)
class ToolProposal:
    proposal_id: str
    proposed_at: datetime
    tool_name: str
    arguments: Mapping[str, object]
    proposer: ToolProposer
    context: ToolProposalContext
    authorization_status: str = "pending_policy"
    contract_version: str = "1.0"

    def __post_init__(self) -> None:
        if self.contract_version != "1.0" or self.authorization_status != "pending_policy":
            raise ValueError("tool proposal must remain a pending v1.0 proposal")
        try:
            UUID(self.proposal_id)
        except (TypeError, ValueError, AttributeError) as error:
            raise ValueError("proposal id must be a UUID") from error
        if _TOOL_NAME.fullmatch(self.tool_name) is None:
            raise ValueError("tool proposal name is invalid")
        if not isinstance(self.proposed_at, datetime) or self.proposed_at.tzinfo is None:
            raise ValueError("tool proposal timestamp must be timezone-aware")
        if not isinstance(self.arguments, Mapping):
            raise ValueError("tool proposal arguments must be an object")
        object.__setattr__(self, "arguments", _freeze_json(self.arguments))

    @classmethod
    def from_llm_action(
        cls,
        action: ProposedAction,
        *,
        request_id: str,
        session_id: str,
        node_id: str,
        actor_id: str,
        explicit_user_request: bool,
        confirmation_id: str | None = None,
        proposer_id: str = "conversation-llm",
        now: datetime | None = None,
    ) -> ToolProposal:
        if not isinstance(action, ProposedAction) or action.authorization_status != "pending_policy":
            raise ValueError("only inert LLM ProposedAction values may become tool proposals")
        proposed_at = now or datetime.now(timezone.utc)
        return cls(
            proposal_id=str(uuid4()),
            proposed_at=proposed_at,
            tool_name=action.name,
            arguments=action.arguments,
            proposer=ToolProposer(ToolProposerType.LLM, proposer_id),
            context=ToolProposalContext(
                request_id=request_id,
                explicit_user_request=explicit_user_request,
                session_id=session_id,
                node_id=node_id,
                actor_id=actor_id,
                confirmation_id=confirmation_id,
            ),
        )


class ToolRegistry:
    """Server-owned allow-list of reviewed Tool definitions."""

    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if not isinstance(definition, ToolDefinition):
            raise TypeError("only ToolDefinition values can be registered")
        if definition.name in self._definitions:
            raise ValueError("tool definition is already registered")
        self._definitions[definition.name] = definition

    def resolve(self, name: str) -> ToolDefinition | None:
        return self._definitions.get(name)

    def snapshot(self) -> tuple[ToolDefinition, ...]:
        return tuple(self._definitions[name] for name in sorted(self._definitions))
