import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class DevelopmentOpenAIDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.script = (ROOT / "deploy/development/hearthghost-development.sh").read_text(
            encoding="utf-8"
        )
        self.documentation = (ROOT / "deploy/development/README.md").read_text(
            encoding="utf-8"
        )

    def test_openai_is_explicit_and_uses_only_a_read_only_secret_file(self):
        self.assertIn('LLM_ADAPTER="${HEARTHGHOST_LLM_ADAPTER:-fake}"', self.script)
        self.assertIn('podman secret exists "${OPENAI_SECRET_NAME}"', self.script)
        self.assertIn(
            "type=mount,target=${OPENAI_SECRET_TARGET},uid=10001,gid=10001,mode=0400",
            self.script,
        )
        self.assertIn(
            '--env "OPENAI_API_KEY_FILE=/run/secrets/${OPENAI_SECRET_TARGET}"',
            self.script,
        )
        self.assertIn('--llm-adapter "${LLM_ADAPTER}"', self.script)

    def test_provider_network_and_cost_cap_are_openai_only(self):
        self.assertIn('EGRESS_NETWORK="hearthghost-development-egress"', self.script)
        self.assertIn('--network "${EGRESS_NETWORK}:ip=${EGRESS_CONTAINER_IP}"', self.script)
        self.assertIn('--network "${NETWORK}:ip=${CONTAINER_IP}"', self.script)
        self.assertIn('GATEWAY_BIND_IP="${CONTAINER_IP}"', self.script)
        self.assertIn('GATEWAY_BIND_IP="0.0.0.0"', self.script)
        self.assertIn('GATEWAY_RUNTIME_ARGS=(--allow-multi-network-bind)', self.script)
        self.assertIn('--bind "${GATEWAY_BIND_IP}"', self.script)
        self.assertLess(
            self.script.index('--network "${NETWORK}:ip=${CONTAINER_IP}"'),
            self.script.index('--network "${EGRESS_NETWORK}:ip=${EGRESS_CONTAINER_IP}"'),
        )
        self.assertIn('if [[ "${LLM_ADAPTER}" != "openai" ]]', self.script)
        self.assertIn('OPENAI_MAX_OUTPUT_TOKENS="${HEARTHGHOST_OPENAI_MAX_OUTPUT_TOKENS:-256}"', self.script)
        self.assertIn("one API request", self.documentation)

    def test_secret_never_becomes_a_value_or_build_argument(self):
        self.assertNotIn("OPENAI_API_KEY=", self.script)
        self.assertNotIn("--build-arg", self.script)
        self.assertIn("never mounted in fake mode", self.documentation)


if __name__ == "__main__":
    unittest.main()
