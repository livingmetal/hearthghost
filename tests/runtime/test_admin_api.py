from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path

from apps.assistant.src.adapters.development_advertisement_admin import DevelopmentAuditedAdvertisementStore
from apps.assistant.src.adapters.development_state import (
    DevelopmentStateFile,
    LocalDevelopmentAdministratorAuthorizer,
    PersistentNodeRegistry,
)
from apps.assistant.src.modules.capability_administration import CapabilityAdvertisementAdministration
from apps.assistant.src.modules.node_administration import NodeAdministration
from apps.assistant.src.runtime.admin_api import AdminApiServer, _ADMIN_HTML, _ADMIN_JS
from apps.assistant.src.runtime.admin_auth import AdministratorToken


TOKEN = "A" * 43
NOW = datetime(2026, 8, 11, 13, tzinfo=timezone.utc)


class Clock:
    def now(self):
        return NOW


class AdminApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = DevelopmentStateFile(Path(self.temp.name) / "state.json")
        self.registry = PersistentNodeRegistry(self.state)
        self.context = object()
        authorizer = LocalDevelopmentAdministratorAuthorizer(
            self.context,
            "local-admin-api",
        )
        self.node_admin = NodeAdministration(
            authorizer=authorizer,
            store=self.registry,
            capabilities=self.registry,
            clock=Clock(),
        )
        self.advertisement_admin = CapabilityAdvertisementAdministration(
            authorized_context=self.context,
            actor_id="local-admin-api",
            store=DevelopmentAuditedAdvertisementStore(self.state),
            clock=Clock(),
        )
        self.server = AdminApiServer(
            ("127.0.0.1", 0),
            token=AdministratorToken(TOKEN),
            admin_context=self.context,
            node_administration=self.node_admin,
            registry=self.registry,
            advertisement_administration=self.advertisement_admin,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, method, path, body=None, *, token=TOKEN, content_type="application/json"):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        headers = {}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        payload = None
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = content_type
        try:
            connection.request(method, path, body=payload, headers=headers)
            response = connection.getresponse()
            raw = response.read()
            return response.status, dict(response.getheaders()), json.loads(raw) if raw else None
        finally:
            connection.close()

    def enroll(self):
        return self.request(
            "POST",
            "/api/v1/nodes/android-development-01/administration",
            {
                "operation_id": "11111111-1111-4111-8111-111111111111",
                "correlation_id": "admin-enroll",
                "action": "node.enroll",
                "expected_revision": 0,
            },
        )

    def test_unauthenticated_request_does_not_reveal_node_existence(self):
        for path in (
            "/api/v1/nodes/android-development-01",
            "/api/v1/nodes/does-not-exist",
        ):
            with self.subTest(path=path):
                status, headers, body = self.request("GET", path, token=None)
                self.assertEqual(status, 401)
                self.assertEqual(body, {"status": "unauthorized"})
                self.assertEqual(headers.get("Cache-Control"), "no-store")

    def test_enroll_advertise_then_grant_are_separate_audited_mutations(self):
        status, _, enrolled = self.enroll()
        self.assertEqual(status, 200)
        self.assertEqual(enrolled["node"]["revision"], 1)
        self.assertEqual(enrolled["node"]["granted_capabilities"], [])

        status, _, advertised = self.request(
            "POST",
            "/api/v1/nodes/android-development-01/advertisements",
            {
                "correlation_id": "admin-advertise",
                "expected_node_revision": 1,
                "advertisements": [
                    {"name": "conversation.text", "local_authorization_required": False},
                    {"name": "notification.local", "local_authorization_required": True},
                ],
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(advertised["reason"], "advertisements_replaced")

        status, _, node = self.request("GET", "/api/v1/nodes/android-development-01")
        self.assertEqual(status, 200)
        self.assertEqual(node["node"]["granted_capabilities"], [])
        self.assertEqual(
            {item["name"] for item in node["node"]["advertised_capabilities"]},
            {"conversation.text", "notification.local"},
        )

        status, _, granted = self.request(
            "POST",
            "/api/v1/nodes/android-development-01/administration",
            {
                "operation_id": "22222222-2222-4222-8222-222222222222",
                "correlation_id": "admin-grant-notification",
                "action": "node.capability.grant",
                "expected_revision": 1,
                "capability": "notification.local",
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("notification.local", granted["node"]["granted_capabilities"])
        self.assertEqual(granted["node"]["revision"], 2)
        self.assertEqual(self.registry.audit_event_count, 3)

    def test_notification_advertisement_without_local_gate_is_rejected(self):
        self.enroll()
        status, _, body = self.request(
            "POST",
            "/api/v1/nodes/android-development-01/advertisements",
            {
                "correlation_id": "admin-bad-ad",
                "expected_node_revision": 1,
                "advertisements": [
                    {"name": "notification.local", "local_authorization_required": False}
                ],
            },
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["reason"], "malformed_request")
        self.assertEqual(self.registry.audit_event_count, 1)

    def test_stale_revision_is_conflict_without_mutation(self):
        self.enroll()
        self.request(
            "POST",
            "/api/v1/nodes/android-development-01/administration",
            {
                "operation_id": "33333333-3333-4333-8333-333333333333",
                "correlation_id": "admin-trust",
                "action": "node.trust.set",
                "expected_revision": 1,
                "trust_state": "trusted",
            },
        )
        status, _, body = self.request(
            "POST",
            "/api/v1/nodes/android-development-01/administration",
            {
                "operation_id": "44444444-4444-4444-8444-444444444444",
                "correlation_id": "admin-stale",
                "action": "node.trust.set",
                "expected_revision": 1,
                "trust_state": "restricted",
            },
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["reason"], "revision_conflict")
        self.assertEqual(self.registry.get_node("android-development-01").trust_state.value, "trusted")

    def test_wrong_token_and_wrong_media_type_fail_before_domain_mutation(self):
        body = {
            "operation_id": "55555555-5555-4555-8555-555555555555",
            "correlation_id": "admin-enroll",
            "action": "node.enroll",
            "expected_revision": 0,
        }
        status, _, _ = self.request(
            "POST",
            "/api/v1/nodes/android-development-01/administration",
            body,
            token="B" * 43,
        )
        self.assertEqual(status, 401)
        self.assertIsNone(self.registry.get_node("android-development-01"))
        status, _, response = self.request(
            "POST",
            "/api/v1/nodes/android-development-01/administration",
            body,
            content_type="text/plain",
        )
        self.assertEqual(status, 415)
        self.assertEqual(response["status"], "json_required")
        self.assertIsNone(self.registry.get_node("android-development-01"))

    def test_console_does_not_embed_or_persist_bearer_token(self):
        combined = _ADMIN_HTML + _ADMIN_JS
        self.assertNotIn(TOKEN, combined)
        self.assertNotIn("localStorage", combined)
        self.assertNotIn("sessionStorage", combined)
        self.assertNotIn("document.cookie", combined)
        self.assertIn('credentials:"omit"', _ADMIN_JS)
        self.assertIn('window.addEventListener("pagehide"', _ADMIN_JS)

    def test_listener_refuses_non_loopback_bind(self):
        with self.assertRaisesRegex(ValueError, "only to loopback"):
            AdminApiServer(
                ("0.0.0.0", 0),
                token=AdministratorToken(TOKEN),
                admin_context=self.context,
                node_administration=self.node_admin,
                registry=self.registry,
                advertisement_administration=self.advertisement_admin,
            )


if __name__ == "__main__":
    unittest.main()
