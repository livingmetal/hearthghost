import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class DevelopmentPrincipalDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.script = (ROOT / "deploy/development/hearthghost-development.sh").read_text(
            encoding="utf-8"
        )
        self.documentation = (ROOT / "deploy/development/README.md").read_text(
            encoding="utf-8"
        )

    def test_principal_binding_is_explicit_and_fail_closed_by_default(self):
        self.assertIn(
            'MEMORY_PRINCIPAL_BINDING="${HEARTHGHOST_MEMORY_PRINCIPAL_BINDING:-}"',
            self.script,
        )
        self.assertIn('if [[ -z "${MEMORY_PRINCIPAL_BINDING}" ]]', self.script)
        self.assertIn('--memory-principal "${MEMORY_PRINCIPAL_BINDING}"', self.script)
        self.assertNotIn("--memory-principal windows-development-01", self.script)

    def test_documentation_keeps_principal_separate_from_node_authority(self):
        self.assertIn("authorization decision", self.documentation)
        self.assertIn("never converted into a Node trust or capability grant", self.documentation)
        self.assertIn("separate Node ID", self.documentation)


if __name__ == "__main__":
    unittest.main()
