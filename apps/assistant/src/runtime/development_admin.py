"""Local-only administration CLI for the rootless development runtime."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from apps.assistant.src.adapters.development_state import (
    DevelopmentStateFile,
    LocalDevelopmentAdministratorAuthorizer,
    PersistentCredentialRepository,
    PersistentNodeRegistry,
)
from apps.assistant.src.modules.node_administration import (
    AdministrationAction,
    AdministrationRequest,
    NodeAdministration,
)
from apps.assistant.src.modules.node_security import (
    CapabilityAdvertisement,
    CredentialRecord,
    CredentialStatus,
    NodeTrustState,
    SystemClock,
)


DEFAULT_ACTOR_ID = "kaiser-development-admin"


def main(arguments: list[str] | None = None) -> int:
    parser = _parser()
    options = parser.parse_args(arguments)
    state = DevelopmentStateFile(options.state)
    credentials = PersistentCredentialRepository(state)
    registry = PersistentNodeRegistry(state)

    if options.command == "provision-credential":
        now = datetime.now(timezone.utc)
        certificate_pem = Path(options.certificate).read_text(encoding="ascii")
        record = CredentialRecord(
            credential_id=options.credential_id,
            node_id=options.node_id,
            credential_type="x509",
            issued_at=now,
            status=CredentialStatus.ACTIVE,
            expires_at=now + timedelta(days=options.expires_days),
        )
        fingerprint = credentials.provision_certificate(
            record=record,
            certificate_pem=certificate_pem,
        )
        _print(
            command=options.command,
            outcome="provisioned",
            node_id=options.node_id,
            credential_id=options.credential_id,
            certificate_sha256=fingerprint,
        )
        return 0

    if options.command == "revoke-credential":
        record = credentials.get(options.credential_id)
        if record is None:
            parser.error("credential does not exist")
        if record.status is not CredentialStatus.ACTIVE:
            parser.error("credential is already terminal")
        credentials.replace(
            replace(
                record,
                status=CredentialStatus.REVOKED,
                revoked_at=datetime.now(timezone.utc),
            )
        )
        _print(
            command=options.command,
            outcome="revoked",
            node_id=record.node_id,
            credential_id=record.credential_id,
        )
        return 0

    if options.command == "advertise":
        registry.replace_advertisements(
            options.node_id,
            tuple(
                CapabilityAdvertisement(capability, False)
                for capability in options.capability
            ),
        )
        _print(
            command=options.command,
            outcome="recorded_without_grant",
            node_id=options.node_id,
            capabilities=sorted(options.capability),
        )
        return 0

    if options.command == "show":
        record = registry.get_node(options.node_id)
        node = registry.get(options.node_id)
        _print(
            command=options.command,
            outcome="found" if record else "not_found",
            node_id=options.node_id,
            trust_state=record.trust_state.value if record else None,
            revision=record.revision if record else None,
            advertised_capabilities=(
                sorted(item.name for item in node.advertised_capabilities)
                if node
                else []
            ),
            granted_capabilities=(
                sorted(record.granted_capabilities) if record else []
            ),
        )
        return 0 if record else 1

    context = object()
    administration = NodeAdministration(
        authorizer=LocalDevelopmentAdministratorAuthorizer(
            context,
            DEFAULT_ACTOR_ID,
        ),
        store=registry,
        capabilities=registry,
        clock=SystemClock(),
    )
    current = registry.get_node(options.node_id)
    if options.command == "enroll":
        action = AdministrationAction.ENROLL_NODE
        expected_revision = 0
        trust_state = None
        capability = None
    else:
        if current is None:
            parser.error("Node is not enrolled")
        expected_revision = current.revision
        trust_state = None
        capability = getattr(options, "capability", None)
        action = {
            "trust": AdministrationAction.SET_TRUST,
            "grant": AdministrationAction.GRANT_CAPABILITY,
            "revoke-capability": AdministrationAction.REVOKE_CAPABILITY,
            "revoke-node": AdministrationAction.REVOKE_NODE,
        }[options.command]
        if options.command == "trust":
            trust_state = NodeTrustState(options.state_value)

    result = administration.administer(
        context,
        AdministrationRequest(
            operation_id=str(uuid4()),
            correlation_id=options.correlation_id,
            action=action,
            node_id=options.node_id,
            expected_revision=expected_revision,
            trust_state=trust_state,
            capability=capability,
        ),
    )
    _print(
        command=options.command,
        outcome="succeeded" if result.succeeded else "denied",
        reason_code=result.reason.value,
        node_id=options.node_id,
        revision=result.record.revision if result.record else None,
    )
    return 0 if result.succeeded else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Administer development Node state without a network API"
    )
    parser.add_argument("--state", required=True)
    parser.add_argument(
        "--correlation-id",
        default="development-admin-cli",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    provision = subparsers.add_parser("provision-credential")
    _node(provision)
    provision.add_argument("--credential-id", required=True)
    provision.add_argument("--certificate", required=True)
    provision.add_argument("--expires-days", type=_expires_days, default=365)

    revoke_credential = subparsers.add_parser("revoke-credential")
    revoke_credential.add_argument("--credential-id", required=True)

    advertise = subparsers.add_parser("advertise")
    _node(advertise)
    advertise.add_argument("--capability", action="append", required=True)

    for command in ("enroll", "revoke-node", "show"):
        child = subparsers.add_parser(command)
        _node(child)

    trust = subparsers.add_parser("trust")
    _node(trust)
    trust.add_argument(
        "--state-value",
        choices=["untrusted", "trusted", "restricted"],
        required=True,
    )

    for command in ("grant", "revoke-capability"):
        child = subparsers.add_parser(command)
        _node(child)
        child.add_argument("--capability", required=True)

    return parser


def _node(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--node-id", required=True)


def _expires_days(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 365:
        raise argparse.ArgumentTypeError("expires-days must be between 1 and 365")
    return parsed


def _print(**values: object) -> None:
    print(json.dumps(values, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
