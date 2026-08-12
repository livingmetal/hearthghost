from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest
from uuid import uuid4

from apps.assistant.src.adapters.home_assistant_readonly import (
    HomeAssistantEntityReadToolAdapter,
    HomeAssistantProtocolError,
    HomeAssistantReadClient,
    HomeAssistantRestReadTransport,
    home_assistant_entity_read_tool_definition,
    home_assistant_read_capability_definitions,
)
from apps.assistant.src.modules.policy import ToolPolicyEngine
from apps.assistant.src.modules.smart_home_registry import (
    AuthorizedToolRequestContext,
    CapabilityRegistry,
    DeviceAdministrationAction,
    DeviceAdministrationRequest,
    SmartHomeDeviceRegistry,
    SmartHomePolicyContextResolver,
    VerifiedDeviceAdministrator,
)
from apps.assistant.src.modules.tool_execution import GuardedToolExecutor
from apps.assistant.src.modules.tools import ActorRole, ToolProposal, ToolRegistry
from apps.assistant.src.ports.home_assistant import HomeAssistantHttpResponse
from apps.assistant.src.ports.llm import ProposedAction


NOW = datetime(2026, 8, 13, 2, 0, tzinfo=timezone.utc)
TOKEN = "t" * 64


class FakeHttpResponse:
    def __init__(self, status, body, content_type="application/json"):
        self.status = status
        self._body = body
        self._content_type = content_type

    def read(self, maximum):
        return self._body

    def getheader(self, name, default=""):
        return self._content_type if name.lower() == "content-type" else default


class FakeConnection:
    def __init__(self, response):
        self.response = response
        self.requests = []
        self.closed = False

    def request(self, method, path, headers=None):
        self.requests.append((method, path, dict(headers or {})))

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


class FakeTransport:
    def __init__(self, states):
        self.states = {state["entity_id"]: state for state in states}
        self.calls = []

    def get(self, path):
        self.calls.append(path)
        if path == "/api/":
            return response({"message": "API running."})
        if path == "/api/states":
            return response(list(self.states.values()))
        prefix = "/api/states/"
        if path.startswith(prefix):
            entity_id = path[len(prefix):]
            state = self.states.get(entity_id)
            return response(state, 200) if state is not None else response({}, 404)
        raise AssertionError(f"unexpected path {path}")


def response(payload, status=200):
    return HomeAssistantHttpResponse(
        status,
        "application/json; charset=utf-8",
        json.dumps(payload).encode("utf-8"),
    )


def entity(entity_id, state, **attributes):
    return {
        "entity_id": entity_id,
        "state": state,
        "last_changed": "2026-08-13T01:59:00+00:00",
        "attributes": attributes,
    }


class AllowingDeviceAdministrator:
    def authorize(self, context, action, device_id):
        if context != "admin":
            return None
        return VerifiedDeviceAdministrator("owner", action, device_id)


def admin_request(action, record, capability=None):
    return DeviceAdministrationRequest(
        operation_id=str(uuid4()),
        action=action,
        device_id=record.device_id,
        expected_revision=record.revision,
        capability=capability,
    )


class HomeAssistantReadonlyTests(unittest.TestCase):
    def test_transport_requires_encrypted_origin_except_loopback(self):
        with self.assertRaisesRegex(ValueError, "require HTTPS"):
            HomeAssistantRestReadTransport("http://homeassistant.local:8123", TOKEN)
        with self.assertRaisesRegex(ValueError, "fixed origin"):
            HomeAssistantRestReadTransport("https://user:pass@ha.example/", TOKEN)
        # Local same-host development may use plaintext without putting a bearer token on the LAN.
        HomeAssistantRestReadTransport("http://127.0.0.1:8123", TOKEN)
        HomeAssistantRestReadTransport("https://ha.internal.example", TOKEN)

    def test_transport_sends_bearer_only_to_allowlisted_get_state_path(self):
        connection = FakeConnection(FakeHttpResponse(200, b'{"entity_id":"light.room","state":"on","attributes":{}}'))
        transport = HomeAssistantRestReadTransport(
            "https://ha.internal.example",
            TOKEN,
            connection_factory=lambda *args: connection,
        )
        result = transport.get("/api/states/light.room")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(connection.requests), 1)
        method, path, headers = connection.requests[0]
        self.assertEqual(method, "GET")
        self.assertEqual(path, "/api/states/light.room")
        self.assertEqual(headers["Authorization"], f"Bearer {TOKEN}")
        self.assertTrue(connection.closed)
        self.assertFalse(hasattr(transport, "post"))

        with self.assertRaisesRegex(HomeAssistantProtocolError, "not allow-listed"):
            transport.get("/api/camera_proxy/camera.living_room")
        with self.assertRaisesRegex(HomeAssistantProtocolError, "not allow-listed"):
            transport.get("/api/services/light/turn_on")
        self.assertEqual(len(connection.requests), 1)

    def test_discovery_exposes_only_reviewed_read_domains_and_no_camera(self):
        transport = FakeTransport(
            [
                entity("light.living_room", "on", friendly_name="Living Room"),
                entity("sensor.room_temp", "23.4", friendly_name="Temperature", device_class="temperature", unit_of_measurement="°C"),
                entity("sensor.room_humidity", "45", device_class="humidity", unit_of_measurement="%"),
                entity("camera.living_room", "streaming", friendly_name="Camera"),
                entity("switch.heater", "off", friendly_name="Heater"),
            ]
        )
        client = HomeAssistantReadClient(transport)
        self.assertTrue(client.ping())
        observations = client.discover_supported_devices()
        by_external_id = {item.external_id: item for item in observations}
        self.assertEqual(
            set(by_external_id),
            {"light.living_room", "sensor.room_temp", "sensor.room_humidity"},
        )
        self.assertEqual(
            by_external_id["light.living_room"].advertised_capabilities,
            frozenset({"home.entity.read", "home.light.read"}),
        )
        self.assertNotIn("camera.living_room", by_external_id)
        self.assertNotIn("switch.heater", by_external_id)

    def test_malformed_or_wrong_entity_response_fails_closed(self):
        transport = FakeTransport([entity("light.other", "on")])
        client = HomeAssistantReadClient(transport)
        with self.assertRaisesRegex(HomeAssistantProtocolError, "not found"):
            client.get_state("light.missing")
        with self.assertRaisesRegex(ValueError, "entity_id"):
            client.get_state("../../api/services/light/turn_on")

    def _approved_stack(self):
        fake_transport = FakeTransport(
            [entity("light.living_room", "on", friendly_name="Living Room Light")]
        )
        client = HomeAssistantReadClient(fake_transport)
        capabilities = CapabilityRegistry()
        for definition in home_assistant_read_capability_definitions():
            capabilities.register(definition)
        devices = SmartHomeDeviceRegistry(
            capabilities,
            authorizer=AllowingDeviceAdministrator(),
            clock=lambda: NOW,
        )
        record = devices.observe(client.discover_supported_devices()[0])
        trusted = devices.administer(
            "admin",
            admin_request(DeviceAdministrationAction.TRUST_DEVICE, record),
        ).record
        granted = devices.administer(
            "admin",
            admin_request(
                DeviceAdministrationAction.GRANT_CAPABILITY,
                trusted,
                "home.entity.read",
            ),
        ).record
        tool_registry = ToolRegistry()
        tool_registry.register(home_assistant_entity_read_tool_definition())
        policy = ToolPolicyEngine(tool_registry, clock=lambda: NOW)
        resolver = SmartHomePolicyContextResolver(devices)
        proposal = ToolProposal.from_llm_action(
            ProposedAction("home.entity.read", {"device_id": granted.device_id}),
            request_id="req-1",
            session_id="session-1",
            node_id="phone-1",
            actor_id="owner",
            explicit_user_request=True,
            now=NOW,
        )
        authorized = AuthorizedToolRequestContext(
            request_id="req-1",
            actor_id="owner",
            roles=frozenset({ActorRole.HOUSEHOLD_MEMBER}),
            explicit_user_request=True,
            active_session=True,
            session_id="session-1",
            node_id="phone-1",
        )
        adapter = HomeAssistantEntityReadToolAdapter(client, devices)
        executor = GuardedToolExecutor(
            tool_registry,
            {"home.entity.read": adapter},
            policy_version=policy.policy_version,
            clock=lambda: NOW,
        )
        return fake_transport, devices, granted, policy, resolver, proposal, authorized, executor

    def test_read_runs_only_after_registry_policy_and_executor_all_allow(self):
        (
            transport,
            devices,
            granted,
            policy,
            resolver,
            proposal,
            authorized,
            executor,
        ) = self._approved_stack()
        calls_before = len(transport.calls)
        decision = policy.evaluate(proposal, resolver.resolve(proposal, authorized))
        self.assertTrue(decision.allowed)
        result = executor.execute(proposal, decision)
        self.assertTrue(result.executed)
        self.assertEqual(result.reason_code, "home_assistant_state_read")
        self.assertEqual(result.output["state"], "on")
        self.assertEqual(transport.calls[calls_before:], ["/api/states/light.living_room"])

    def test_adapter_rechecks_revocation_after_policy_allow_before_http_get(self):
        (
            transport,
            devices,
            granted,
            policy,
            resolver,
            proposal,
            authorized,
            executor,
        ) = self._approved_stack()
        decision = policy.evaluate(proposal, resolver.resolve(proposal, authorized))
        self.assertTrue(decision.allowed)
        revoked = devices.administer(
            "admin",
            admin_request(DeviceAdministrationAction.REVOKE_DEVICE, granted),
        )
        self.assertTrue(revoked.succeeded)
        calls_before = len(transport.calls)
        result = executor.execute(proposal, decision)
        self.assertFalse(result.executed)
        self.assertEqual(result.reason_code, "device_not_currently_authorized")
        self.assertEqual(len(transport.calls), calls_before)


if __name__ == "__main__":
    unittest.main()
