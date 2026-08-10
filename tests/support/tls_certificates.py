"""Ephemeral, test-only certificate fixtures shared by security tests."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


OPENSSL = shutil.which("openssl")
SERVER_NAME = "core.test.invalid"


@dataclass(frozen=True)
class TestCertificates:
    ca: Path
    server_certificate: Path
    server_key: Path
    node_certificate: Path
    node_key: Path
    unknown_node_certificate: Path
    unknown_node_key: Path


def create_test_certificates(directory: Path) -> TestCertificates:
    if OPENSSL is None:
        raise RuntimeError("OpenSSL CLI is required for TLS fixtures")
    ca_key = directory / "TEST-ONLY-ca.key"
    ca_certificate = directory / "TEST-ONLY-ca.pem"
    _run_openssl(
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-sha256",
        "-days",
        "2",
        "-subj",
        "/CN=HearthGhost TEST ONLY Ephemeral CA",
        "-addext",
        "basicConstraints=critical,CA:TRUE,pathlen:0",
        "-addext",
        "keyUsage=critical,keyCertSign,cRLSign",
        "-keyout",
        str(ca_key),
        "-out",
        str(ca_certificate),
    )
    server_certificate, server_key = _create_leaf_certificate(
        directory,
        name="server",
        subject="/CN=HearthGhost TEST ONLY Core",
        ca_certificate=ca_certificate,
        ca_key=ca_key,
        extended_key_usage="serverAuth",
        subject_alt_name=f"DNS:{SERVER_NAME}",
    )
    node_certificate, node_key = _create_leaf_certificate(
        directory,
        name="node-a",
        subject="/CN=HearthGhost TEST ONLY Node A",
        ca_certificate=ca_certificate,
        ca_key=ca_key,
        extended_key_usage="clientAuth",
    )
    unknown_certificate, unknown_key = _create_leaf_certificate(
        directory,
        name="unknown-node",
        subject="/CN=HearthGhost TEST ONLY Unknown Node",
        ca_certificate=ca_certificate,
        ca_key=ca_key,
        extended_key_usage="clientAuth",
    )
    return TestCertificates(
        ca=ca_certificate,
        server_certificate=server_certificate,
        server_key=server_key,
        node_certificate=node_certificate,
        node_key=node_key,
        unknown_node_certificate=unknown_certificate,
        unknown_node_key=unknown_key,
    )


def _create_leaf_certificate(
    directory: Path,
    *,
    name: str,
    subject: str,
    ca_certificate: Path,
    ca_key: Path,
    extended_key_usage: str,
    subject_alt_name: str | None = None,
) -> tuple[Path, Path]:
    private_key = directory / f"TEST-ONLY-{name}.key"
    signing_request = directory / f"TEST-ONLY-{name}.csr"
    certificate = directory / f"TEST-ONLY-{name}.pem"
    extensions = directory / f"TEST-ONLY-{name}.ext"
    extension_lines = [
        "basicConstraints=critical,CA:FALSE",
        "keyUsage=critical,digitalSignature,keyEncipherment",
        f"extendedKeyUsage={extended_key_usage}",
        "subjectKeyIdentifier=hash",
        "authorityKeyIdentifier=keyid,issuer",
    ]
    if subject_alt_name is not None:
        extension_lines.append(f"subjectAltName={subject_alt_name}")
    extensions.write_text("\n".join(extension_lines) + "\n", encoding="ascii")
    _run_openssl(
        "req",
        "-new",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-sha256",
        "-subj",
        subject,
        "-keyout",
        str(private_key),
        "-out",
        str(signing_request),
    )
    _run_openssl(
        "x509",
        "-req",
        "-in",
        str(signing_request),
        "-CA",
        str(ca_certificate),
        "-CAkey",
        str(ca_key),
        "-CAcreateserial",
        "-days",
        "2",
        "-sha256",
        "-extfile",
        str(extensions),
        "-out",
        str(certificate),
    )
    return certificate, private_key


def _run_openssl(*arguments: str) -> None:
    subprocess.run(
        [OPENSSL, *arguments],
        check=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=15,
    )
