"""Development-only PKI workflow; private Node keys are never accepted."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path

from apps.assistant.src.modules.node_security import IDENTIFIER_PATTERN


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage the development Node PKI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    initialize = subparsers.add_parser("initialize-authority")
    initialize.add_argument("--authority-dir", required=True)

    server = subparsers.add_parser("issue-server")
    server.add_argument("--authority-dir", required=True)
    server.add_argument("--output-dir", required=True)
    server.add_argument("--server-ip", required=True)

    inspect = subparsers.add_parser("inspect-node-csr")
    inspect.add_argument("--csr", required=True)

    sign = subparsers.add_parser("sign-node-csr")
    sign.add_argument("--authority-dir", required=True)
    sign.add_argument("--csr", required=True)
    sign.add_argument("--node-id", required=True)
    sign.add_argument("--approve-sha256", required=True)
    sign.add_argument("--certificate-out", required=True)

    options = parser.parse_args(arguments)
    _require_openssl()
    if options.command == "initialize-authority":
        _initialize_authority(Path(options.authority_dir))
        _print(command=options.command, outcome="initialized")
        return 0
    if options.command == "issue-server":
        _issue_server(
            Path(options.authority_dir),
            Path(options.output_dir),
            options.server_ip,
        )
        _print(
            command=options.command,
            outcome="issued",
            server_ip=options.server_ip,
        )
        return 0

    csr = Path(options.csr)
    fingerprint = _csr_fingerprint(csr)
    if options.command == "inspect-node-csr":
        subject = _command(
            "openssl",
            "req",
            "-in",
            str(csr),
            "-noout",
            "-subject",
        ).stdout.decode("utf-8", errors="strict").strip()
        _print(
            command=options.command,
            outcome="inspected_not_signed",
            csr_sha256=fingerprint,
            subject=subject,
        )
        return 0

    if IDENTIFIER_PATTERN.fullmatch(options.node_id) is None:
        parser.error("node-id is invalid")
    if not secrets.compare_digest(fingerprint, options.approve_sha256.lower()):
        parser.error("approved SHA-256 does not match the inspected CSR")
    _sign_node_csr(
        Path(options.authority_dir),
        csr,
        options.node_id,
        Path(options.certificate_out),
    )
    _print(
        command=options.command,
        outcome="signed_after_explicit_fingerprint_approval",
        node_id=options.node_id,
        csr_sha256=fingerprint,
    )
    return 0


def _initialize_authority(directory: Path) -> None:
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(directory, 0o700)
    _command(
        "openssl",
        "req",
        "-x509",
        "-newkey",
        "rsa:3072",
        "-nodes",
        "-keyout",
        str(directory / "ca.key"),
        "-out",
        str(directory / "ca.crt"),
        "-subj",
        "/CN=HearthGhost Development CA",
        "-days",
        "3650",
        "-sha256",
        "-addext",
        "basicConstraints=critical,CA:TRUE,pathlen:0",
        "-addext",
        "keyUsage=critical,keyCertSign,cRLSign",
        "-addext",
        "subjectKeyIdentifier=hash",
    )
    os.chmod(directory / "ca.key", 0o600)
    os.chmod(directory / "ca.crt", 0o644)


def _issue_server(authority: Path, output: Path, server_ip: str) -> None:
    _require_authority(authority)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(output, 0o700)
    with tempfile.TemporaryDirectory(prefix="hearthghost-server-csr-") as temporary:
        csr = Path(temporary) / "server.csr"
        extensions = Path(temporary) / "server.ext"
        extensions.write_text(
            "\n".join(
                (
                    "basicConstraints=critical,CA:FALSE",
                    "keyUsage=critical,digitalSignature",
                    "extendedKeyUsage=serverAuth",
                    f"subjectAltName=IP:{server_ip}",
                    "subjectKeyIdentifier=hash",
                    "authorityKeyIdentifier=keyid,issuer",
                )
            )
            + "\n",
            encoding="ascii",
        )
        _command(
            "openssl",
            "req",
            "-new",
            "-newkey",
            "rsa:3072",
            "-nodes",
            "-keyout",
            str(output / "server.key"),
            "-out",
            str(csr),
            "-subj",
            "/CN=HearthGhost Development Gateway",
            "-sha256",
        )
        _sign(authority, csr, output / "server.crt", extensions, days=397)
    shutil.copyfile(authority / "ca.crt", output / "client-ca.crt")
    os.chmod(output / "server.key", 0o600)
    os.chmod(output / "server.crt", 0o644)
    os.chmod(output / "client-ca.crt", 0o644)


def _sign_node_csr(
    authority: Path,
    csr: Path,
    node_id: str,
    certificate_out: Path,
) -> None:
    _require_authority(authority)
    _command("openssl", "req", "-in", str(csr), "-verify", "-noout")
    certificate_out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hearthghost-node-sign-") as temporary:
        extensions = Path(temporary) / "node.ext"
        extensions.write_text(
            "\n".join(
                (
                    "basicConstraints=critical,CA:FALSE",
                    "keyUsage=critical,digitalSignature",
                    "extendedKeyUsage=clientAuth",
                    f"subjectAltName=URI:urn:hearthghost:node:{node_id}",
                    "subjectKeyIdentifier=hash",
                    "authorityKeyIdentifier=keyid,issuer",
                )
            )
            + "\n",
            encoding="ascii",
        )
        _sign(authority, csr, certificate_out, extensions, days=365)
    os.chmod(certificate_out, 0o600)


def _sign(
    authority: Path,
    csr: Path,
    certificate: Path,
    extensions: Path,
    *,
    days: int,
) -> None:
    _command(
        "openssl",
        "x509",
        "-req",
        "-in",
        str(csr),
        "-CA",
        str(authority / "ca.crt"),
        "-CAkey",
        str(authority / "ca.key"),
        "-set_serial",
        "0x" + secrets.token_hex(16),
        "-out",
        str(certificate),
        "-days",
        str(days),
        "-sha256",
        "-extfile",
        str(extensions),
    )


def _csr_fingerprint(csr: Path) -> str:
    _command("openssl", "req", "-in", str(csr), "-verify", "-noout")
    der = _command(
        "openssl",
        "req",
        "-in",
        str(csr),
        "-outform",
        "DER",
    ).stdout
    return hashlib.sha256(der).hexdigest()


def _require_authority(directory: Path) -> None:
    if (
        not directory.is_dir()
        or directory.stat().st_mode & 0o077
        or not (directory / "ca.key").is_file()
        or (directory / "ca.key").stat().st_mode & 0o077
        or not (directory / "ca.crt").is_file()
    ):
        raise PermissionError("development authority is missing or not private")


def _require_openssl() -> None:
    if shutil.which("openssl") is None:
        raise RuntimeError("OpenSSL CLI is required")


def _command(*arguments: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            arguments,
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError("OpenSSL operation failed") from error


def _print(**values: object) -> None:
    print(json.dumps(values, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
