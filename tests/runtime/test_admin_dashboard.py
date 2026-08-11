from __future__ import annotations

import http.client
import json
import threading
import unittest

from apps.assistant.src.runtime.admin_dashboard import (
    DASHBOARD_HTML,
    DASHBOARD_JS,
    AdminDashboardServer,
)


class StatusSource:
    def status(self):
        return {
            "service": "hearthghost-core",
            "status": "degraded",
            "storage": "persistent_postgresql",
            "contracts_loaded": 12,
            "boundaries": {
                "node_gateway": "loaded",
                "policy": "deny_only",
                "notification_routing": "explicit_principal_to_node",
            },
            "readiness_reasons": ["policy_rules_not_configured"],
        }


class AdminDashboardTests(unittest.TestCase):
    def setUp(self):
        self.server = AdminDashboardServer(("127.0.0.1", 0), StatusSource())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        try:
            connection.request(method, path)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_dashboard_server_is_literal_loopback_only(self):
        with self.assertRaisesRegex(ValueError, "only to loopback"):
            AdminDashboardServer(("0.0.0.0", 0), StatusSource())
        with self.assertRaisesRegex(ValueError, "literal loopback"):
            AdminDashboardServer(("localhost", 0), StatusSource())

    def test_html_and_status_are_read_only_and_no_store(self):
        status, headers, body = self.request("GET", "/admin")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertEqual(body, DASHBOARD_HTML)

        status, headers, body = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        document = json.loads(body)
        self.assertEqual(document["storage"], "persistent_postgresql")
        self.assertEqual(document["boundaries"]["policy"], "deny_only")
        self.assertNotIn("dsn", json.dumps(document).lower())
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_all_common_write_methods_are_rejected(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                status, _, body = self.request(method, "/api/status")
                self.assertEqual(status, 405)
                self.assertEqual(json.loads(body)["status"], "method_not_allowed")

    def test_dashboard_javascript_uses_dom_text_not_html_injection(self):
        script = DASHBOARD_JS.decode("utf-8")
        self.assertIn("textContent", script)
        self.assertIn("replaceChildren", script)
        self.assertNotIn("innerHTML", script)
        self.assertNotIn("eval(", script)
        self.assertNotIn("localStorage", script)
        self.assertNotIn("sessionStorage", script)

    def test_html_has_no_inline_script_or_secret_fields(self):
        html = DASHBOARD_HTML.decode("utf-8")
        self.assertIn('<script src="/dashboard.js" defer></script>', html)
        self.assertNotIn("<script>", html)
        for sensitive in ("private key", "postgresql://", "api key", "bearer token"):
            self.assertNotIn(sensitive, html.lower())


if __name__ == "__main__":
    unittest.main()
