from __future__ import annotations

import hashlib
import os
import ssl
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from apps.assistant.src.adapters.development_state import (
    DevelopmentStateFile,
    LocalDevelopmentAdministratorAuthorizer,
    PersistentCertificateIdentityResolver,
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
from apps.assistant.src.runtime.development_pki import main as pki_main
from apps.assistant.src.runtime.development_server import DevelopmentGatewayServer
from tests.support.tls_certificates import OPENSSL


NODE_ID = "android-development-01"
CREDENTIAL_ID = "android-development-credential-01"


@unittest.skipUnless(os.name == "posix", "development state targets rootless Linux")
class DevelopmentStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="hearthghost-state-")
        self.root = Path(self.temporary.name)
        os.chmod(self.root, 0o700)
        self.path = self.root / "state.json"
        self.state = DevelopmentStateFile(self.path)
        self.credentials = PersistentCredentialRepository(self.state)
        self.registry = PersistentNodeRegistry(self.state)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_state_is_private_and_survives_new_adapter_instances(self):
        now = datetime.now(timezone.utc)
        record = CredentialRecord(
            CREDENTIAL_ID,
            NODE_ID,
            "x509",
            now,
            CredentialStatus.ACTIVE,
            expires_at=now + timedelta(days=1),
        )
        certificate_der = b"test-only-certificate-der"
        fingerprint = hashlib.sha256(certificate_der).hexdigest()
        self.credentials.register(record)
        self.state.update(
            lambda document: document["certificate_bindings"].__setitem__(
                fingerprint,
                {"credential_id": CREDENTIAL_ID, "node_id": NODE_ID},
            )
        )
        self.registry.replace_advertisements(
            NODE_ID,
            (CapabilityAdvertisement("conversation.text", False),),
        )
        administration = self._administration()
        enrolled = self._administer(administration, AdministrationAction.ENROLL_NODE)
        self.assertTrue(enrolled.succeeded)
        trusted = self._administer(
            administration,
            AdministrationAction.SET_TRUST,
            trust_state=NodeTrustState.TRUSTED,
        )
        self.assertTrue(trusted.succeeded)
        granted = self._administer(
            administration,
            AdministrationAction.GRANT_CAPABILITY,
            capability="conversation.text",
        )
        self.assertTrue(granted.succeeded)

        reopened = DevelopmentStateFile(self.path)
        reopened_registry = PersistentNodeRegistry(reopened)
        reopened_credentials = PersistentCredentialRepository(reopened)
        reopened_resolver = PersistentCertificateIdentityResolver(reopened)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(reopened_registry.get_node(NODE_ID).revision, 3)
        self.assertEqual(
            reopened_registry.get_node(NODE_ID).trust_state,
            NodeTrustState.TRUSTED,
        )
        self.assertEqual(
            reopened_credentials.get(CREDENTIAL_ID).status,
            CredentialStatus.ACTIVE,
        )
        self.assertEqual(
            reopened_resolver.resolve(certificate_der).credential_id,
            CREDENTIAL_ID,
        )

    def test_credential_revocation_is_visible_without_reopening_state(self):
        now = datetime.now(timezone.utc)
        record = CredentialRecord(
            CREDENTIAL_ID,
            NODE_ID,
            "x509",
            now,
            CredentialStatus.ACTIVE,
            expires_at=now + timedelta(days=1),
        )
        self.credentials.register(record)
        second_repository = PersistentCredentialRepository(
            DevelopmentStateFile(self.path)
        )
        second_repository.replace(
            CredentialRecord(
                CREDENTIAL_ID,
                NODE_ID,
                "x509",
                now,
                CredentialStatus.REVOKED,
                expires_at=record.expires_at,
                revoked_at=now + timedelta(seconds=1),
            )
        )
        self.assertEqual(
            self.credentials.get(CREDENTIAL_ID).status,
            CredentialStatus.REVOKED,
        )

    def test_insecure_state_file_is_rejected(self):
        os.chmod(self.path, 0o644)
        with self.assertRaises(PermissionError):
            DevelopmentStateFile(self.path)

    def _administration(self) -> NodeAdministration:
        self.context = object()
        return NodeAdministration(
            authorizer=LocalDevelopmentAdministratorAuthorizer(
                self.context,
                "test-development-admin",
            ),
            store=self.registry,
            capabilities=self.registry,
            clock=SystemClock(),
        )

    def _administer(
        self,
        administration: NodeAdministration,
        action: AdministrationAction,
        *,
        trust_state: NodeTrustState | None = None,
        capability: str | None = None,
    ):
        current = self.registry.get_node(NODE_ID)
        return administration.administer(
            self.context,
            AdministrationRequest(
                operation_id=str(uuid4()),
                correlation_id="development-state-test",
                action=action,
                node_id=NODE_ID,
                expected_revision=current.revision if current else 0,
                trust_state=trust_state,
                capability=capability,
            ),
        )


class DevelopmentGatewayConfigurationTests(unittest.TestCase):
    def test_gateway_rejects_wildcard_and_loopback_bindings(self):
        for address in ("0.0.0.0", "127.0.0.1"):
            with self.subTest(address=address), self.assertRaises(ValueError):
                DevelopmentGatewayServer(
                    bind_address=address,
                    port=8443,
                    tls=object(),
                    node_protocol=object(),
                    conversation_protocol=object(),
                )


@unittest.skipUnless(OPENSSL, "OpenSSL CLI is required for development PKI tests")
class DevelopmentPkiTests(unittest.TestCase):
    def test_csr_requires_matching_explicit_approval_before_signing(self):
        with tempfile.TemporaryDirectory(prefix="hearthghost-pki-") as temporary:
            root = Path(temporary)
            authority = root / "authority"
            runtime_tls = root / "runtime-tls"
            node_key = root / "node.key"
            node_csr = root / "node.csr"
            node_certificate = root / "node.crt"
            self.assertEqual(
                pki_main(
                    ["initialize-authority", "--authority-dir", str(authority)]
                ),
                0,
            )
            self.assertEqual(
                pki_main(
                    [
                        "issue-server",
                        "--authority-dir",
                        str(authority),
                        "--output-dir",
                        str(runtime_tls),
                        "--server-ip",
                        "192.168.55.100",
                    ]
                ),
                0,
            )
            subprocess.run(
                [
                    OPENSSL,
                    "req",
                    "-new",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-keyout",
                    str(node_key),
                    "-out",
                    str(node_csr),
                    "-subj",
                    "/CN=Android Development Node",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            der = subprocess.run(
                [OPENSSL, "req", "-in", str(node_csr), "-outform", "DER"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            ).stdout
            approved = hashlib.sha256(der).hexdigest()
            with self.assertRaises(SystemExit):
                pki_main(
                    [
                        "sign-node-csr",
                        "--authority-dir",
                        str(authority),
                        "--csr",
                        str(node_csr),
                        "--node-id",
                        NODE_ID,
                        "--approve-sha256",
                        "0" * 64,
                        "--certificate-out",
                        str(node_certificate),
                    ]
                )
            self.assertFalse(node_certificate.exists())
            self.assertEqual(
                pki_main(
                    [
                        "sign-node-csr",
                        "--authority-dir",
                        str(authority),
                        "--csr",
                        str(node_csr),
                        "--node-id",
                        NODE_ID,
                        "--approve-sha256",
                        approved,
                        "--certificate-out",
                        str(node_certificate),
                    ]
                ),
                0,
            )
            self.assertTrue(node_certificate.is_file())
            self.assertEqual((authority / "ca.key").stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
