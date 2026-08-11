from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from apps.assistant.src.runtime.admin_auth import AdministratorToken, read_administrator_token


TOKEN = "A" * 43


class AdminAuthTests(unittest.TestCase):
    def test_constant_time_bearer_boundary_accepts_exact_token_only(self):
        token = AdministratorToken(TOKEN)
        self.assertTrue(token.accepts_authorization_header(f"Bearer {TOKEN}"))
        for value in (
            None,
            "",
            TOKEN,
            f"bearer {TOKEN}",
            f"Bearer {'B' * 43}",
            f"Bearer {TOKEN} extra",
            "Bearer short",
        ):
            with self.subTest(value=value):
                self.assertFalse(token.accepts_authorization_header(value))
        self.assertNotIn(TOKEN, repr(token))

    def test_secret_file_must_be_regular_owner_only_and_one_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "admin-token"
            path.write_text(TOKEN + "\n", encoding="ascii")
            os.chmod(path, 0o600)
            loaded = read_administrator_token(path)
            self.assertTrue(loaded.accepts_authorization_header(f"Bearer {TOKEN}"))

            os.chmod(path, 0o640)
            with self.assertRaises(PermissionError):
                read_administrator_token(path)

            os.chmod(path, 0o700)
            with self.assertRaises(PermissionError):
                read_administrator_token(path)

    def test_symlink_secret_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.write_text(TOKEN + "\n", encoding="ascii")
            os.chmod(target, 0o600)
            link = root / "link"
            link.symlink_to(target)
            with self.assertRaises(PermissionError):
                read_administrator_token(link)

    def test_multiline_whitespace_and_non_base64url_tokens_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "admin-token"
            for value in (
                TOKEN + "\n" + TOKEN,
                " " + TOKEN,
                "!" * 43,
            ):
                with self.subTest(value=value[:8]):
                    path.write_text(value, encoding="ascii")
                    os.chmod(path, 0o600)
                    with self.assertRaises(ValueError):
                        read_administrator_token(path)


if __name__ == "__main__":
    unittest.main()
