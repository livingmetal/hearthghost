"""Audited capability-advertisement mutations for development JSON state."""

from __future__ import annotations

from datetime import datetime

from apps.assistant.src.adapters.development_state import (
    DevelopmentStateFile,
    PersistentNodeRegistry,
)
from apps.assistant.src.modules.node_administration import NodeAdministrationRecord
from apps.assistant.src.modules.node_security import (
    CAPABILITY_PATTERN,
    SENSITIVE_LOCAL_CAPABILITIES,
    CapabilityAdvertisement,
)


class DevelopmentAuditedAdvertisementStore:
    def __init__(self, state: DevelopmentStateFile) -> None:
        self._state = state
        self._registry = PersistentNodeRegistry(state)

    def get_node(self, node_id: str) -> NodeAdministrationRecord | None:
        return self._registry.get_node(node_id)

    def replace_advertisements_audited(
        self,
        *,
        node_id: str,
        expected_node_revision: int,
        advertisements: tuple[CapabilityAdvertisement, ...],
        actor_id: str,
        correlation_id: str,
        occurred_at: datetime,
        event_id: str,
    ) -> bool:
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise ValueError("advertisement audit time must be timezone-aware")
        _validate_advertisements(advertisements)

        def replace(document: dict[str, object]) -> bool:
            nodes = document.get("nodes")
            ad_state = document.get("advertisements")
            events = document.get("audit_events")
            if not isinstance(nodes, dict) or not isinstance(ad_state, dict) or not isinstance(events, list):
                raise RuntimeError("development administration state is invalid")
            node = nodes.get(node_id)
            if not isinstance(node, dict):
                return False
            revision = node.get("revision")
            if (
                not isinstance(revision, int)
                or isinstance(revision, bool)
                or revision != expected_node_revision
            ):
                return False
            ad_state[node_id] = [
                {
                    "name": item.name,
                    "local_authorization_required": item.local_authorization_required,
                }
                for item in advertisements
            ]
            events.append(
                {
                    "event_id": event_id,
                    "correlation_id": correlation_id,
                    "occurred_at": occurred_at.isoformat(),
                    "category": "administration",
                    "action": "node.capability.advertisements.replace",
                    "actor_type": "user",
                    "actor_id": actor_id,
                    "decision": "allow",
                    "result": "success",
                    "node_id": node_id,
                    "capability": None,
                }
            )
            return True

        return self._state.update(replace)


def _validate_advertisements(advertisements: object) -> None:
    if not isinstance(advertisements, tuple) or len(advertisements) > 32:
        raise ValueError("advertisements are invalid")
    names: set[str] = set()
    for item in advertisements:
        if (
            not isinstance(item, CapabilityAdvertisement)
            or CAPABILITY_PATTERN.fullmatch(item.name) is None
            or not isinstance(item.local_authorization_required, bool)
            or item.name in names
            or (
                item.name in SENSITIVE_LOCAL_CAPABILITIES
                and not item.local_authorization_required
            )
        ):
            raise ValueError("advertisements violate the Node capability boundary")
        names.add(item.name)
