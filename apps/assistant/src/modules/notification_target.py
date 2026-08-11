"""Explicit notification routing with no creator-origin or presence inference."""

from __future__ import annotations

from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.modules.node_security import IDENTIFIER_PATTERN


class DenyingNotificationTargetResolver:
    def resolve(self, scope: str, scope_id: str) -> str | None:
        return None


class StaticNotificationTargetResolver:
    def __init__(self, bindings: dict[tuple[MemoryScope, str], str]) -> None:
        normalized: dict[tuple[MemoryScope, str], str] = {}
        for key, node_id in bindings.items():
            if (
                not isinstance(key, tuple)
                or len(key) != 2
                or not isinstance(key[0], MemoryScope)
                or not isinstance(key[1], str)
                or not key[1]
                or len(key[1]) > 128
                or not isinstance(node_id, str)
                or IDENTIFIER_PATTERN.fullmatch(node_id) is None
            ):
                raise ValueError("notification target binding is invalid")
            if key in normalized:
                raise ValueError("notification target binding is duplicated")
            normalized[key] = node_id
        self._bindings = normalized

    def resolve(self, scope: str, scope_id: str) -> str | None:
        if not isinstance(scope, str) or not isinstance(scope_id, str) or not scope_id:
            return None
        try:
            parsed_scope = MemoryScope(scope)
        except ValueError:
            return None
        return self._bindings.get((parsed_scope, scope_id))
