import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class DevelopmentPostgresDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.script = (ROOT / "deploy/development/hearthghost-development.sh").read_text(
            encoding="utf-8"
        )
        self.documentation = (ROOT / "deploy/development/README.md").read_text(
            encoding="utf-8"
        )

    def test_postgres_is_explicit_and_uses_a_read_only_podman_secret(self):
        self.assertIn(
            'POSTGRES_SECRET_NAME="${HEARTHGHOST_POSTGRES_SECRET_NAME:-}"',
            self.script,
        )
        self.assertIn('podman secret exists "${POSTGRES_SECRET_NAME}"', self.script)
        self.assertIn(
            "type=mount,target=${POSTGRES_SECRET_TARGET},uid=10001,gid=10001,mode=0400",
            self.script,
        )
        self.assertIn(
            '--postgres-dsn-secret "/run/secrets/${POSTGRES_SECRET_TARGET}"',
            self.script,
        )

    def test_postgres_secret_is_not_an_environment_value_or_build_argument(self):
        self.assertNotIn("POSTGRES_DSN=", self.script)
        self.assertNotIn("--build-arg", self.script)
        self.assertNotIn("--env POSTGRES", self.script)
        self.assertIn("sslmode=require", self.documentation)
        self.assertIn("never put in Git", self.documentation)


if __name__ == "__main__":
    unittest.main()
