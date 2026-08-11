"""Owner-only administrator token loading and constant-time bearer validation."""

from __future__ import annotations

import hmac
import os
import re
from pathlib import Path


TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43,128}$")
MAX_AUTHORIZATION_HEADER = 256


class AdministratorToken:
    def __init__(self, token: str) -> None:
        if not isinstance(token, str) or TOKEN_PATTERN.fullmatch(token) is None:
            raise ValueError("administrator token must be 43-128 base64url characters")
        self._token = token

    def __repr__(self) -> str:
        return "AdministratorToken(<redacted>)"

    def accepts_authorization_header(self, value: object) -> bool:
        if not isinstance(value, str) or not 1 <= len(value) <= MAX_AUTHORIZATION_HEADER:
            return False
        prefix = "Bearer "
        if not value.startswith(prefix):
            return False
        candidate = value[len(prefix):]
        if TOKEN_PATTERN.fullmatch(candidate) is None:
            return False
        return hmac.compare_digest(candidate, self._token)


def read_administrator_token(path: str | os.PathLike[str]) -> AdministratorToken:
    file_path = Path(path)
    if file_path.is_symlink():
        raise PermissionError("administrator token secret may not be a symlink")
    try:
        stat = file_path.stat()
    except OSError as error:
        raise RuntimeError("administrator token secret is unavailable") from error
    if not file_path.is_file() or stat.st_mode & 0o077:
        raise PermissionError("administrator token secret must be a regular owner-only file")
    if stat.st_size < 44 or stat.st_size > 130:
        raise ValueError("administrator token secret size is invalid")
    try:
        value = file_path.read_text(encoding="ascii")
    except (OSError, UnicodeError) as error:
        raise RuntimeError("administrator token secret is unreadable") from error
    if value.endswith("\n"):
        value = value[:-1]
    if "\n" in value or "\r" in value or value != value.strip():
        raise ValueError("administrator token secret must contain one token line")
    return AdministratorToken(value)
