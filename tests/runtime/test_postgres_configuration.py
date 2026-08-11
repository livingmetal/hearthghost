from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from apps.assistant.src.runtime.postgres_configuration import read_postgres_dsn


class PostgresConfigurationTests(unittest.TestCase):
    def test_reads_single_line_dsn(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "dsn"
            path.write_text("postgresql://hearthghost:secret@db/hearthghost?sslmode=require\n", encoding="utf-8")
            self.assertEqual(
                read_postgres_dsn(path),
                "postgresql://hearthghost:secret@db/hearthghost?sslmode=require",
            )

    def test_rejects_symlink_and_multiline_secret(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.write_text("postgresql://x\nsecond-line", encoding="utf-8")
            link = root / "link"
            link.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlink"):
                read_postgres_dsn(link)
            with self.assertRaisesRegex(ValueError, "invalid"):
                read_postgres_dsn(target)


if __name__ == "__main__":
    unittest.main()
