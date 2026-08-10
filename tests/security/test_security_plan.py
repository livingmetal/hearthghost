import json
import unittest
from pathlib import Path


PLAN = Path(__file__).with_name("planned-denial-cases.json")

REQUIRED_CASES = {
    "unauthorized-camera-request",
    "unknown-node",
    "revoked-node",
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

    def test_foundation_does_not_claim_unimplemented_behavior(self):
        for case in self.plan["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual("deny", case["expected_decision"])
                self.assertEqual("not_implemented", case["implementation_status"])


if __name__ == "__main__":
    unittest.main()
