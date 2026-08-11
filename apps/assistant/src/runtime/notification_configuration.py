"""Startup parsing for explicit principal-to-notification-Node routing."""

from __future__ import annotations

from collections.abc import Iterable

from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.modules.node_security import IDENTIFIER_PATTERN
from apps.assistant.src.modules.notification_target import StaticNotificationTargetResolver


def parse_notification_target_bindings(values: Iterable[str]) -> StaticNotificationTargetResolver:
    bindings: dict[tuple[MemoryScope, str], str] = {}
    used_nodes: set[str] = set()
    for raw in values:
        if not isinstance(raw, str) or "=" not in raw:
            raise ValueError("notification target binding must be scope:scope_id=node_id")
        principal, separator, node_id = raw.partition("=")
        scope_name, scope_separator, scope_id = principal.partition(":")
        if (
            separator != "="
            or scope_separator != ":"
            or not scope_id
            or len(scope_id) > 128
            or IDENTIFIER_PATTERN.fullmatch(node_id) is None
        ):
            raise ValueError("notification target binding must be scope:scope_id=node_id")
        try:
            scope = MemoryScope(scope_name)
        except ValueError as error:
            raise ValueError("notification target scope must be user or household") from error
        key = (scope, scope_id)
        if key in bindings:
            raise ValueError("notification target binding contains duplicate principal")
        if node_id in used_nodes:
            raise ValueError("notification target Node may belong to only one principal route")
        bindings[key] = node_id
        used_nodes.add(node_id)
    return StaticNotificationTargetResolver(bindings)
