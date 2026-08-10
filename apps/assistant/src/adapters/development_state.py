"""Restrictive single-host persistence for the rootless development runtime.

This adapter stores only public Node administration, credential lifecycle, and
certificate fingerprint bindings. It never stores a private key or provider
credential. The file is re-read for every protected lookup so local revocation
takes effect without exposing an administration API.
"""

from __future__ import annotations

import hashlib
import json
import os
import ssl
import tempfile
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Callable, Iterator, TypeVar

try:
    import fcntl
except ImportError:  # pragma: no cover - the deployment target is Linux
    fcntl = None

from apps.assistant.src.modules.node_administration import (
    AdministrationAction,
    AdministrationAuditEvent,
    AdministrationMutation,
    AdministrationRequest,
    NodeAdministrationRecord,
    StoreApplyOutcome,
    StoreApplyResult,
    StoredAdministrationOperation,
    VerifiedAdministrator,
)
from apps.assistant.src.modules.node_security import (
    CAPABILITY_PATTERN,
    SENSITIVE_LOCAL_CAPABILITIES,
    CapabilityAdvertisement,
    CredentialRecord,
    CredentialStatus,
    NodeRecord,
    NodeTrustState,
    VerifiedCredential,
)


STATE_VERSION = 1
_T = TypeVar("_T")


def _empty_state() -> dict[str, object]:
    return {
        "version": STATE_VERSION,
        "nodes": {},
        "operations": {},
        "audit_events": [],
        "advertisements": {},
        "credentials": {},
        "certificate_bindings": {},
    }


class DevelopmentStateFile:
    """Atomically read and update one mode-0600 JSON state file."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        if fcntl is None:
            raise RuntimeError("development state requires Linux file locking")
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self._thread_lock = RLock()
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        _require_private_directory(self.path.parent)
        if not self.path.exists():
            self._write_unlocked(_empty_state())
        _require_private_file(self.path)

    def read(self, reader: Callable[[dict[str, object]], _T]) -> _T:
        with self._locked(exclusive=False):
            return reader(self._load_unlocked())

    def update(self, writer: Callable[[dict[str, object]], _T]) -> _T:
        with self._locked(exclusive=True):
            document = self._load_unlocked()
            result = writer(document)
            self._write_unlocked(document)
            return result

    @contextmanager
    def _locked(self, *, exclusive: bool) -> Iterator[None]:
        with self._thread_lock:
            descriptor = os.open(
                self.lock_path,
                os.O_RDWR | os.O_CREAT,
                0o600,
            )
            try:
                os.fchmod(descriptor, 0o600)
                fcntl.flock(
                    descriptor,
                    fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH,
                )
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    def _load_unlocked(self) -> dict[str, object]:
        _require_private_file(self.path)
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RuntimeError("development state is unreadable") from error
        expected = set(_empty_state())
        if (
            not isinstance(document, dict)
            or set(document) != expected
            or document.get("version") != STATE_VERSION
            or not all(
                isinstance(document.get(name), dict)
                for name in (
                    "nodes",
                    "operations",
                    "advertisements",
                    "credentials",
                    "certificate_bindings",
                )
            )
            or not isinstance(document.get("audit_events"), list)
        ):
            raise RuntimeError("development state has an unsupported shape")
        return document

    def _write_unlocked(self, document: dict[str, object]) -> None:
        payload = json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ) + "\n"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=self.path.name + ".",
            dir=self.path.parent,
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, self.path)
            os.chmod(self.path, 0o600)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise


class PersistentCredentialRepository:
    def __init__(self, state: DevelopmentStateFile) -> None:
        self._state = state

    def get(self, credential_id: str) -> CredentialRecord | None:
        return self._state.read(
            lambda document: _credential_from_document(
                _mapping(document, "credentials").get(credential_id)
            )
        )

    def register(self, record: CredentialRecord) -> None:
        def register(document: dict[str, object]) -> None:
            records = _mapping(document, "credentials")
            if record.credential_id in records:
                raise ValueError("credential already exists")
            records[record.credential_id] = _credential_document(record)

        self._state.update(register)

    def replace(self, record: CredentialRecord) -> None:
        def replace_record(document: dict[str, object]) -> None:
            records = _mapping(document, "credentials")
            prior = _credential_from_document(records.get(record.credential_id))
            if prior is None:
                raise ValueError("credential does not exist")
            if prior.node_id != record.node_id:
                raise ValueError("credential Node binding cannot change")
            if prior.status is not CredentialStatus.ACTIVE and record != prior:
                raise ValueError("terminal credential lifecycle cannot change")
            records[record.credential_id] = _credential_document(record)

        self._state.update(replace_record)

    def bind_certificate(
        self,
        *,
        certificate_pem: str,
        credential_id: str,
        node_id: str,
    ) -> str:
        fingerprint = certificate_fingerprint(certificate_pem)

        def bind(document: dict[str, object]) -> None:
            record = _credential_from_document(
                _mapping(document, "credentials").get(credential_id)
            )
            if record is None or record.node_id != node_id:
                raise ValueError("credential binding does not match registered Node")
            bindings = _mapping(document, "certificate_bindings")
            prior = bindings.get(fingerprint)
            candidate = {"credential_id": credential_id, "node_id": node_id}
            if prior is not None and prior != candidate:
                raise ValueError("certificate is already bound")
            bindings[fingerprint] = candidate

        self._state.update(bind)
        return fingerprint

    def provision_certificate(
        self,
        *,
        record: CredentialRecord,
        certificate_pem: str,
    ) -> str:
        """Atomically register lifecycle metadata and its exact certificate."""

        fingerprint = certificate_fingerprint(certificate_pem)

        def provision(document: dict[str, object]) -> None:
            records = _mapping(document, "credentials")
            bindings = _mapping(document, "certificate_bindings")
            if record.credential_id in records:
                raise ValueError("credential already exists")
            if fingerprint in bindings:
                raise ValueError("certificate is already bound")
            records[record.credential_id] = _credential_document(record)
            bindings[fingerprint] = {
                "credential_id": record.credential_id,
                "node_id": record.node_id,
            }

        self._state.update(provision)
        return fingerprint


class PersistentCertificateIdentityResolver:
    """Resolve an exact DER certificate fingerprint to public identity evidence."""

    def __init__(self, state: DevelopmentStateFile) -> None:
        self._state = state

    def resolve(self, peer_certificate_der: bytes) -> VerifiedCredential | None:
        if not isinstance(peer_certificate_der, bytes) or not peer_certificate_der:
            return None
        fingerprint = hashlib.sha256(peer_certificate_der).hexdigest()

        def resolve(document: dict[str, object]) -> VerifiedCredential | None:
            binding = _mapping(document, "certificate_bindings").get(fingerprint)
            if (
                not isinstance(binding, dict)
                or set(binding) != {"credential_id", "node_id"}
                or not isinstance(binding.get("credential_id"), str)
                or not isinstance(binding.get("node_id"), str)
            ):
                return None
            return VerifiedCredential(
                binding["credential_id"],
                binding["node_id"],
            )

        return self._state.read(resolve)


class PersistentNodeRegistry:
    """File-backed Gateway view and atomic Node administration store."""

    def __init__(self, state: DevelopmentStateFile) -> None:
        self._state = state

    def get(self, node_id: str) -> NodeRecord | None:
        def read(document: dict[str, object]) -> NodeRecord | None:
            record = _node_record_from_document(
                _mapping(document, "nodes").get(node_id)
            )
            if record is None:
                return None
            advertisements = _advertisements_from_document(
                _mapping(document, "advertisements").get(node_id, [])
            )
            return NodeRecord(
                node_id=record.node_id,
                trust_state=record.trust_state,
                advertised_capabilities=advertisements,
                granted_capabilities=record.granted_capabilities,
            )

        return self._state.read(read)

    def get_node(self, node_id: str) -> NodeAdministrationRecord | None:
        return self._state.read(
            lambda document: _node_record_from_document(
                _mapping(document, "nodes").get(node_id)
            )
        )

    def get_operation(
        self, operation_id: str
    ) -> StoredAdministrationOperation | None:
        return self._state.read(
            lambda document: _operation_from_document(
                _mapping(document, "operations").get(operation_id)
            )
        )

    def is_advertised(self, node_id: str, capability: str) -> bool:
        return self._state.read(
            lambda document: any(
                item.name == capability
                for item in _advertisements_from_document(
                    _mapping(document, "advertisements").get(node_id, [])
                )
            )
        )

    def replace_advertisements(
        self,
        node_id: str,
        advertisements: tuple[CapabilityAdvertisement, ...],
    ) -> None:
        names: set[str] = set()
        for item in advertisements:
            if (
                not isinstance(item, CapabilityAdvertisement)
                or CAPABILITY_PATTERN.fullmatch(item.name) is None
                or item.name in names
                or (
                    item.name in SENSITIVE_LOCAL_CAPABILITIES
                    and not item.local_authorization_required
                )
            ):
                raise ValueError("advertisements violate the Node capability boundary")
            names.add(item.name)

        def replace(document: dict[str, object]) -> None:
            _mapping(document, "advertisements")[node_id] = [
                {
                    "name": item.name,
                    "local_authorization_required": item.local_authorization_required,
                }
                for item in advertisements
            ]

        self._state.update(replace)

    def apply(self, mutation: AdministrationMutation) -> StoreApplyResult:
        def apply_mutation(document: dict[str, object]) -> StoreApplyResult:
            operations = _mapping(document, "operations")
            prior = _operation_from_document(
                operations.get(mutation.request.operation_id)
            )
            if prior is not None:
                if prior.request == mutation.request:
                    return StoreApplyResult(StoreApplyOutcome.IDEMPOTENT, prior.record)
                return StoreApplyResult(StoreApplyOutcome.IDEMPOTENCY_CONFLICT)

            nodes = _mapping(document, "nodes")
            current = _node_record_from_document(nodes.get(mutation.request.node_id))
            if mutation.request.action is AdministrationAction.ENROLL_NODE:
                revision_matches = (
                    current is None and mutation.request.expected_revision == 0
                )
            else:
                revision_matches = (
                    current is not None
                    and current.revision == mutation.request.expected_revision
                )
            if not revision_matches:
                return StoreApplyResult(StoreApplyOutcome.REVISION_CONFLICT)

            stored = StoredAdministrationOperation(
                mutation.request,
                mutation.record,
                mutation.audit_event,
            )
            nodes[mutation.request.node_id] = _node_record_document(mutation.record)
            operations[mutation.request.operation_id] = _operation_document(stored)
            audit_events = document["audit_events"]
            if not isinstance(audit_events, list):
                raise RuntimeError("development audit state is invalid")
            audit_events.append(_audit_document(mutation.audit_event))
            return StoreApplyResult(StoreApplyOutcome.APPLIED, mutation.record)

        return self._state.update(apply_mutation)

    @property
    def audit_event_count(self) -> int:
        return self._state.read(lambda document: len(document["audit_events"]))


class LocalDevelopmentAdministratorAuthorizer:
    """Authorize only a process-local unforgeable context used by the CLI."""

    def __init__(self, context: object, actor_id: str) -> None:
        self._context = context
        self._actor_id = actor_id

    def authorize(
        self,
        context: object,
        action: AdministrationAction,
        node_id: str,
    ) -> VerifiedAdministrator | None:
        if context is not self._context:
            return None
        return VerifiedAdministrator(self._actor_id, action, node_id)


def certificate_fingerprint(certificate_pem: str) -> str:
    try:
        der = ssl.PEM_cert_to_DER_cert(certificate_pem)
    except ValueError as error:
        raise ValueError("certificate must be one PEM certificate") from error
    return hashlib.sha256(der).hexdigest()


def _mapping(document: dict[str, object], name: str) -> dict[str, object]:
    value = document.get(name)
    if not isinstance(value, dict):
        raise RuntimeError(f"development {name} state is invalid")
    return value


def _require_private_directory(path: Path) -> None:
    if path.stat().st_mode & 0o077:
        raise PermissionError("development state directory must not be group/world accessible")


def _require_private_file(path: Path) -> None:
    if not path.is_file() or path.stat().st_mode & 0o077:
        raise PermissionError("development state file must have mode 0600 or stricter")


def _time(value: object) -> datetime:
    if not isinstance(value, str):
        raise RuntimeError("development state timestamp is invalid")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeError("development state timestamp lacks a timezone")
    return parsed


def _optional_time(value: object) -> datetime | None:
    return None if value is None else _time(value)


def _credential_document(record: CredentialRecord) -> dict[str, object]:
    return {
        "credential_id": record.credential_id,
        "node_id": record.node_id,
        "credential_type": record.credential_type,
        "issued_at": record.issued_at.isoformat(),
        "status": record.status.value,
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        "revoked_at": record.revoked_at.isoformat() if record.revoked_at else None,
        "replacement_credential_id": record.replacement_credential_id,
    }


def _credential_from_document(value: object) -> CredentialRecord | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise RuntimeError("development credential state is invalid")
    try:
        return CredentialRecord(
            credential_id=value["credential_id"],
            node_id=value["node_id"],
            credential_type=value["credential_type"],
            issued_at=_time(value["issued_at"]),
            status=CredentialStatus(value["status"]),
            expires_at=_optional_time(value.get("expires_at")),
            revoked_at=_optional_time(value.get("revoked_at")),
            replacement_credential_id=value.get("replacement_credential_id"),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("development credential state is invalid") from error


def _node_record_document(record: NodeAdministrationRecord) -> dict[str, object]:
    return {
        "node_id": record.node_id,
        "trust_state": record.trust_state.value,
        "granted_capabilities": sorted(record.granted_capabilities),
        "revision": record.revision,
        "enrolled_at": record.enrolled_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _node_record_from_document(value: object) -> NodeAdministrationRecord | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise RuntimeError("development Node state is invalid")
    try:
        grants = value["granted_capabilities"]
        if not isinstance(grants, list) or not all(isinstance(item, str) for item in grants):
            raise TypeError
        return NodeAdministrationRecord(
            node_id=value["node_id"],
            trust_state=NodeTrustState(value["trust_state"]),
            granted_capabilities=frozenset(grants),
            revision=value["revision"],
            enrolled_at=_time(value["enrolled_at"]),
            updated_at=_time(value["updated_at"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("development Node state is invalid") from error


def _request_document(request: AdministrationRequest) -> dict[str, object]:
    return {
        "operation_id": request.operation_id,
        "correlation_id": request.correlation_id,
        "action": request.action.value,
        "node_id": request.node_id,
        "expected_revision": request.expected_revision,
        "trust_state": request.trust_state.value if request.trust_state else None,
        "capability": request.capability,
    }


def _request_from_document(value: object) -> AdministrationRequest:
    if not isinstance(value, dict):
        raise RuntimeError("development operation request is invalid")
    try:
        trust_state = value.get("trust_state")
        return AdministrationRequest(
            operation_id=value["operation_id"],
            correlation_id=value["correlation_id"],
            action=AdministrationAction(value["action"]),
            node_id=value["node_id"],
            expected_revision=value["expected_revision"],
            trust_state=(NodeTrustState(trust_state) if trust_state else None),
            capability=value.get("capability"),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("development operation request is invalid") from error


def _audit_document(event: AdministrationAuditEvent) -> dict[str, object]:
    document = asdict(event)
    document["occurred_at"] = event.occurred_at.isoformat()
    return document


def _audit_from_document(value: object) -> AdministrationAuditEvent:
    if not isinstance(value, dict):
        raise RuntimeError("development audit event is invalid")
    try:
        return AdministrationAuditEvent(
            event_id=value["event_id"],
            correlation_id=value["correlation_id"],
            occurred_at=_time(value["occurred_at"]),
            category=value["category"],
            action=value["action"],
            actor_type=value["actor_type"],
            actor_id=value["actor_id"],
            decision=value["decision"],
            result=value["result"],
            node_id=value["node_id"],
            capability=value.get("capability"),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("development audit event is invalid") from error


def _operation_document(operation: StoredAdministrationOperation) -> dict[str, object]:
    return {
        "request": _request_document(operation.request),
        "record": _node_record_document(operation.record),
        "audit_event": _audit_document(operation.audit_event),
    }


def _operation_from_document(value: object) -> StoredAdministrationOperation | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise RuntimeError("development operation state is invalid")
    try:
        return StoredAdministrationOperation(
            _request_from_document(value["request"]),
            _node_record_from_document(value["record"]),
            _audit_from_document(value["audit_event"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("development operation state is invalid") from error


def _advertisements_from_document(
    value: object,
) -> tuple[CapabilityAdvertisement, ...]:
    if not isinstance(value, list):
        raise RuntimeError("development capability state is invalid")
    result = []
    try:
        for item in value:
            if not isinstance(item, dict):
                raise TypeError
            result.append(
                CapabilityAdvertisement(
                    item["name"],
                    item["local_authorization_required"],
                )
            )
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("development capability state is invalid") from error
    return tuple(result)
