"""Audited administrator-only replacement of Node capability advertisements.

Advertisements describe a reviewed Node build surface. They are configuration,
not grants. A separate NodeAdministration grant remains required before Gateway
admission can use an advertised capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import uuid4

from apps.assistant.src.modules.node_administration import NodeAdministrationRecord
from apps.assistant.src.modules.node_security import (
    CAPABILITY_PATTERN,
    IDENTIFIER_PATTERN,
    SENSITIVE_LOCAL_CAPABILITIES,
    CapabilityAdvertisement,
    NodeTrustState,
)
from apps.assistant.src.ports.node_gateway import Clock


MAX_ADVERTISEMENTS = 32


@dataclass(frozen=True)
class AdvertisementAdministrationRequest:
    correlation_id: str
    node_id: str
    expected_node_revision: int
    advertisements: tuple[CapabilityAdvertisement, ...]


@dataclass(frozen=True)
class AdvertisementAdministrationResult:
    succeeded: bool
    reason: str
    advertisements: tuple[CapabilityAdvertisement, ...] = ()


class AuditedAdvertisementStore(Protocol):
    def get_node(self, node_id: str) -> NodeAdministrationRecord | None: ...

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
    ) -> bool: ...


class CapabilityAdvertisementAdministration:
    def __init__(
        self,
        *,
        authorized_context: object,
        actor_id: str,
        store: AuditedAdvertisementStore,
        clock: Clock,
    ) -> None:
        if not _identifier(actor_id):
            raise ValueError("administrator actor_id is invalid")
        self._context = authorized_context
        self._actor_id = actor_id
        self._store = store
        self._clock = clock

    def replace(
        self,
        context: object,
        request: AdvertisementAdministrationRequest,
    ) -> AdvertisementAdministrationResult:
        if context is not self._context:
            return AdvertisementAdministrationResult(False, "administration_denied")
        normalized = _validate_request(request)
        if normalized is None:
            return AdvertisementAdministrationResult(False, "malformed_request")
        try:
            node = self._store.get_node(request.node_id)
        except Exception:
            return AdvertisementAdministrationResult(False, "state_unavailable")
        if node is None:
            return AdvertisementAdministrationResult(False, "node_not_enrolled")
        if node.trust_state is NodeTrustState.REVOKED:
            return AdvertisementAdministrationResult(False, "node_revoked")
        if node.revision != request.expected_node_revision:
            return AdvertisementAdministrationResult(False, "revision_conflict")
        try:
            now = self._clock.now()
        except Exception:
            return AdvertisementAdministrationResult(False, "clock_unavailable")
        if now.tzinfo is None or now.utcoffset() is None:
            return AdvertisementAdministrationResult(False, "clock_invalid")
        try:
            applied = self._store.replace_advertisements_audited(
                node_id=request.node_id,
                expected_node_revision=request.expected_node_revision,
                advertisements=normalized,
                actor_id=self._actor_id,
                correlation_id=request.correlation_id,
                occurred_at=now,
                event_id=str(uuid4()),
            )
        except Exception:
            return AdvertisementAdministrationResult(False, "state_unavailable")
        if not applied:
            return AdvertisementAdministrationResult(False, "revision_conflict")
        return AdvertisementAdministrationResult(
            True,
            "advertisements_replaced",
            normalized,
        )


def _validate_request(
    request: object,
) -> tuple[CapabilityAdvertisement, ...] | None:
    if (
        not isinstance(request, AdvertisementAdministrationRequest)
        or not _identifier(request.node_id)
        or not _identifier(request.correlation_id)
        or not isinstance(request.expected_node_revision, int)
        or isinstance(request.expected_node_revision, bool)
        or request.expected_node_revision <= 0
        or not isinstance(request.advertisements, tuple)
        or len(request.advertisements) > MAX_ADVERTISEMENTS
    ):
        return None
    names: set[str] = set()
    normalized: list[CapabilityAdvertisement] = []
    for item in request.advertisements:
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
            return None
        names.add(item.name)
        normalized.append(item)
    return tuple(normalized)


def _identifier(value: object) -> bool:
    return isinstance(value, str) and IDENTIFIER_PATTERN.fullmatch(value) is not None
