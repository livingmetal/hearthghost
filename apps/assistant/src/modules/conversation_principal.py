"""Explicit Node-to-memory-principal binding for the first memory milestone.

A trusted Node identifies a device, not necessarily the human currently speaking.
This boundary therefore resolves memory scope only from administrator-provisioned
bindings. It never derives a user from Node IDs, LLM output, message text, or
network location.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol

from apps.assistant.src.modules.memory import MemoryScope


class PrincipalAssurance(str, Enum):
    PERSONAL_NODE_BINDING = "personal_node_binding"
    HOUSEHOLD_NODE_BINDING = "household_node_binding"


@dataclass(frozen=True)
class ConversationPrincipal:
    scope: MemoryScope
    scope_id: str
    assurance: PrincipalAssurance
    source_node_id: str


class ConversationPrincipalResolver(Protocol):
    def resolve(self, node_id: str) -> ConversationPrincipal | None:
        """Return only a pre-authorized memory principal or fail closed with None."""


class StaticConversationPrincipalResolver:
    """Small administrator-provisioned resolver for development and early MVP use."""

    def __init__(self, bindings: Mapping[str, ConversationPrincipal]) -> None:
        if not isinstance(bindings, Mapping):
            raise TypeError("principal bindings must be a mapping")
        normalized: dict[str, ConversationPrincipal] = {}
        for node_id, principal in bindings.items():
            _validate_binding(node_id, principal)
            normalized[node_id] = principal
        self._bindings = normalized

    def resolve(self, node_id: str) -> ConversationPrincipal | None:
        if not isinstance(node_id, str) or not node_id:
            return None
        principal = self._bindings.get(node_id)
        if principal is None:
            return None
        # Revalidate on read so accidental mutable-object substitution or future
        # adapter changes cannot silently broaden the scope boundary.
        _validate_binding(node_id, principal)
        return principal


class DenyingConversationPrincipalResolver:
    """Default Core resolver. Memory remains unavailable until explicitly configured."""

    def resolve(self, node_id: str) -> None:
        return None


def _validate_binding(node_id: object, principal: object) -> None:
    if not isinstance(node_id, str) or not node_id or len(node_id) > 128:
        raise ValueError("principal binding node_id is invalid")
    if not isinstance(principal, ConversationPrincipal):
        raise TypeError("principal binding value is invalid")
    if principal.source_node_id != node_id:
        raise ValueError("principal binding source Node does not match key")
    if not isinstance(principal.scope, MemoryScope):
        raise ValueError("principal memory scope is invalid")
    if not isinstance(principal.scope_id, str) or not principal.scope_id or len(principal.scope_id) > 128:
        raise ValueError("principal scope_id is invalid")
    if not isinstance(principal.assurance, PrincipalAssurance):
        raise ValueError("principal assurance is invalid")
    if (
        principal.scope is MemoryScope.USER
        and principal.assurance is not PrincipalAssurance.PERSONAL_NODE_BINDING
    ):
        raise ValueError("user memory requires a personal Node binding")
    if (
        principal.scope is MemoryScope.HOUSEHOLD
        and principal.assurance is not PrincipalAssurance.HOUSEHOLD_NODE_BINDING
    ):
        raise ValueError("household memory requires a household Node binding")
