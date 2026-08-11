"""Startup parsing for explicit development memory principal bindings."""

from __future__ import annotations

from collections.abc import Iterable

from apps.assistant.src.modules.conversation_principal import (
    ConversationPrincipal,
    PrincipalAssurance,
    StaticConversationPrincipalResolver,
)
from apps.assistant.src.modules.memory import MemoryScope


def parse_memory_principal_bindings(
    values: Iterable[str],
) -> StaticConversationPrincipalResolver:
    bindings: dict[str, ConversationPrincipal] = {}
    for raw in values:
        if not isinstance(raw, str) or "=" not in raw:
            raise ValueError("memory principal binding must be node_id=scope:scope_id")
        node_id, separator, target = raw.partition("=")
        scope_name, scope_separator, scope_id = target.partition(":")
        if (
            separator != "="
            or scope_separator != ":"
            or not node_id
            or not scope_id
            or len(node_id) > 128
            or len(scope_id) > 128
        ):
            raise ValueError("memory principal binding must be node_id=scope:scope_id")
        if node_id in bindings:
            raise ValueError("memory principal binding contains duplicate Node")
        if scope_name == "user":
            scope = MemoryScope.USER
            assurance = PrincipalAssurance.PERSONAL_NODE_BINDING
        elif scope_name == "household":
            scope = MemoryScope.HOUSEHOLD
            assurance = PrincipalAssurance.HOUSEHOLD_NODE_BINDING
        else:
            raise ValueError("memory principal scope must be user or household")
        bindings[node_id] = ConversationPrincipal(
            scope=scope,
            scope_id=scope_id,
            assurance=assurance,
            source_node_id=node_id,
        )
    return StaticConversationPrincipalResolver(bindings)
