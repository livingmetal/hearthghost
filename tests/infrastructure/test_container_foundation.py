import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ContainerFoundationTests(unittest.TestCase):
    def setUp(self):
        self.dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        self.dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    def test_test_image_is_non_root_with_dependencies_installed_only_in_runtime_base(self):
        self.assertIn(
            "FROM python:3.13-slim-bookworm AS runtime-base",
            self.dockerfile,
        )
        self.assertIn("FROM runtime-base AS test", self.dockerfile)
        self.assertIn("USER hearthghost", self.dockerfile)
        self.assertIn(
            'CMD ["python", "-m", "unittest", "discover"',
            self.dockerfile,
        )
        runtime_base, later_stages = self.dockerfile.split("FROM runtime-base AS test", maxsplit=1)
        self.assertIn("apt-get install", runtime_base)
        self.assertIn("libpq5", runtime_base)
        self.assertIn("pip install --no-cache-dir -r /tmp/requirements-runtime.txt", runtime_base)
        self.assertNotIn("apt-get", later_stages)
        self.assertNotIn("pip install", later_stages)
        self.assertNotIn("EXPOSE", self.dockerfile)
        self.assertNotIn("VOLUME", self.dockerfile)

    def test_core_image_is_minimal_non_root_and_has_no_embedded_secrets(self):
        self.assertIn("FROM runtime-base AS core", self.dockerfile)
        self.assertIn(
            "COPY --chown=hearthghost:hearthghost apps ./apps",
            self.dockerfile,
        )
        self.assertIn(
            "COPY --chown=hearthghost:hearthghost contracts ./contracts",
            self.dockerfile,
        )
        self.assertNotIn("COPY .env", self.dockerfile)
        self.assertNotIn("COPY secrets", self.dockerfile)

    def test_mock_node_image_is_outbound_only_and_uses_the_runtime_base(self):
        self.assertIn("FROM runtime-base AS mock-node", self.dockerfile)
        self.assertIn(
            'CMD ["python", "-m", "apps.mock_node.src.client", "--check"]',
            self.dockerfile,
        )
        self.assertNotIn("EXPOSE", self.dockerfile)

    def test_client_validation_image_uses_locked_dependencies_and_no_secrets(self):
        self.assertIn("FROM node:22-bookworm-slim AS client-test", self.dockerfile)
        self.assertIn(
            "apps/web-client/package.json apps/web-client/package-lock.json",
            self.dockerfile,
        )
        self.assertIn("npm ci --ignore-scripts --no-audit --no-fund", self.dockerfile)
        self.assertIn("USER node", self.dockerfile)
        self.assertNotIn("OPENAI_API_KEY", self.dockerfile)
        self.assertNotIn("--build-arg", self.dockerfile)

    def test_walking_skeleton_image_reuses_test_base_and_has_no_listener(self):
        self.assertIn("FROM test AS walking-skeleton", self.dockerfile)
        self.assertIn(
            '"tests.integration.test_text_walking_skeleton_e2e"',
            self.dockerfile,
        )
        self.assertIn("FROM runtime-base AS client-node", self.dockerfile)
        self.assertNotIn("EXPOSE", self.dockerfile)

    def test_openai_smoke_image_is_explicit_and_contains_no_secret(self):
        self.assertIn("FROM core AS openai-smoke", self.dockerfile)
        self.assertIn(
            '"apps.assistant.src.runtime.openai_smoke", "--adapter", "openai"',
            self.dockerfile,
        )
        self.assertNotIn("OPENAI_API_KEY", self.dockerfile)
        self.assertNotIn("--build-arg", self.dockerfile)

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

    def test_core_service_is_internal_loopback_only_and_hardened(self):
        required = {
            "target: core",
            'network_mode: "none"',
            "read_only: true",
            "apps.assistant.src.runtime.healthcheck",
            "- no-new-privileges:true",
        }
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.compose)

        self.assertNotIn("ports:", self.compose)
        self.assertNotIn("expose:", self.compose)

    def test_client_test_service_is_network_isolated_and_hardened(self):
        client_service = self.compose.split("  client-test:", maxsplit=1)[1]
        for value in {
            "target: client-test",
            'network_mode: "none"',
            "read_only: true",
            "- ALL",
            "- no-new-privileges:true",
        }:
            with self.subTest(value=value):
                self.assertIn(value, client_service)

        for value in {"ports:", "volumes:", "devices:", "privileged: true"}:
            with self.subTest(value=value):
                self.assertNotIn(value, client_service)

    def test_walking_skeleton_service_is_ephemeral_and_network_isolated(self):
        service = self.compose.split("  walking-skeleton:", maxsplit=1)[1].split(
            "  openai-smoke:", maxsplit=1
        )[0]
        for value in {
            "target: walking-skeleton",
            'network_mode: "none"',
            "read_only: true",
            "- ALL",
            "- no-new-privileges:true",
        }:
            with self.subTest(value=value):
                self.assertIn(value, service)
        self.assertNotIn("ports:", service)
        self.assertNotIn("volumes:", service)

    def test_openai_smoke_is_opt_in_hardened_and_uses_external_secret(self):
        service = self.compose.split("  openai-smoke:", maxsplit=1)[1].split(
            "\nsecrets:", maxsplit=1
        )[0]
        for value in {
            "- provider-smoke",
            "target: openai-smoke",
            "OPENAI_API_KEY_FILE: /run/secrets/openai-api-key",
            "OPENAI_MODEL: gpt-5.6-luna",
            "source: openai_api_key",
            "read_only: true",
            "- ALL",
            "- no-new-privileges:true",
        }:
            with self.subTest(value=value):
                self.assertIn(value, service)
        self.assertNotIn("network_mode: host", service)
        self.assertNotIn("ports:", service)
        self.assertNotIn("volumes:", service)
        self.assertIn("external: true", self.compose)
        self.assertIn("name: hearthghost-openai-api-key", self.compose)

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
