import json
import unittest
from importlib import import_module
from pathlib import Path


PLAN = Path(__file__).with_name("planned-denial-cases.json")

REQUIRED_CASES = {
    "unauthorized-camera-request",
    "unknown-node",
    "revoked-credential",
    "unknown-credential",
    "expired-credential",
    "untrusted-node-protected-operation",
    "ungranted-capability",
    "unadvertised-capability",
    "replayed-node-request",
    "malformed-node-identity",
    "ambiguous-security-state",
    "llm-hard-policy-modification",
    "default-cloud-image-upload",
    "critical-action-without-confirmation",
    "policy-service-unavailable",
}


class SecurityPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads(PLAN.read_text(encoding="utf-8"))

    def test_required_denial_cases_are_planned(self):
        cases = {case["id"] for case in self.plan["cases"]}
        self.assertEqual(REQUIRED_CASES, cases)

    def test_plan_distinguishes_executable_and_deferred_cases(self):
        for case in self.plan["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual("deny", case["expected_decision"])
                self.assertIn(
                    case["implementation_status"],
                    {"implemented", "not_implemented"},
                )
                if case["implementation_status"] == "implemented":
                    reference = case.get("executable_test", "")
                    module_name, class_name, method_name = reference.rsplit(".", 2)
                    test_class = getattr(import_module(module_name), class_name)
                    self.assertTrue(callable(getattr(test_class, method_name)))
                else:
                    self.assertNotIn("executable_test", case)


if __name__ == "__main__":
    unittest.main()
