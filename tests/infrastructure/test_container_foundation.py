import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ContainerFoundationTests(unittest.TestCase):
    def setUp(self):
        self.dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        self.dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    def test_test_image_is_non_root_and_dependency_free(self):
        self.assertIn("FROM python:3.13-slim-bookworm AS test", self.dockerfile)
        self.assertIn("USER hearthghost", self.dockerfile)
        self.assertIn(
            'CMD ["python", "-m", "unittest", "discover"',
            self.dockerfile,
        )
        self.assertNotIn("apt-get", self.dockerfile)
        self.assertNotIn("pip install", self.dockerfile)
        self.assertNotIn("EXPOSE", self.dockerfile)
        self.assertNotIn("VOLUME", self.dockerfile)

    def test_compose_test_service_preserves_security_baseline(self):
        required = {
            'network_mode: "none"',
            "read_only: true",
            "- ALL",
            "- no-new-privileges:true",
            "- /tmp:size=64m,mode=1777",
        }
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.compose)

        forbidden = {
            "privileged: true",
            "network_mode: host",
            "/var/run/docker.sock",
            "volumes:",
            "ports:",
            "devices:",
            "pid: host",
            "ipc: host",
            "CAP_SYS_ADMIN",
        }
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, self.compose)

    def test_build_context_excludes_local_and_sensitive_state(self):
        ignored = set(self.dockerignore.splitlines())
        self.assertTrue(
            {
                ".git",
                ".env",
                ".env.*",
                "secrets",
                "*.key",
                "*.p12",
                "*.pfx",
                "**/__pycache__",
                "node_modules",
                "dist",
                "build",
            }.issubset(ignored)
        )


if __name__ == "__main__":
    unittest.main()
