"""Read-only Home Assistant REST adapter with a hard API-path allow-list.

The credential is adapter-owned.  No POST/service-call, camera, template, event,
or arbitrary URL capability is exposed through this module.
"""

from __future__ import annotations

from dataclasses import dataclass
import http.client
import ipaddress
import json
import re
import ssl
from types import MappingProxyType
from typing import Callable, Mapping
from urllib.parse import urlsplit

from apps.assistant.src.modules.smart_home_registry import (
    CapabilityDefinition,
    DeviceObservation,
    DeviceTrustState,
    SmartHomeDeviceRegistry,
)
from apps.assistant.src.modules.tools import (
    ActorRole,
    AuditLevel,
    ConfirmationPolicy,
    ToolDefinition,
    ToolEffect,
    ToolProposal,
    ToolRequiredContext,
    ToolRiskLevel,
)
from apps.assistant.src.ports.home_assistant import (
    HomeAssistantHttpResponse,
    HomeAssistantReadTransport,
)
from apps.assistant.src.ports.tools import ToolAdapterResult


_ENTITY_ID = re.compile(r"[a-z0-9_]+\.[a-z0-9_]+")
_STATE_PATH = re.compile(r"/api/states/[a-z0-9_]+\.[a-z0-9_]+")
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_ENTITIES = 4096


class HomeAssistantAdapterError(RuntimeError):
    """Base adapter failure whose text never contains the access token."""


class HomeAssistantUnavailableError(HomeAssistantAdapterError):
    pass


class HomeAssistantProtocolError(HomeAssistantAdapterError):
    pass


def _is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class HomeAssistantRestReadTransport:
    """Exact-origin GET transport for the narrow state API subset."""

    def __init__(
        self,
        base_url: str,
        access_token: str,
        *,
        timeout_seconds: float = 5.0,
        ssl_context: ssl.SSLContext | None = None,
        connection_factory: Callable[..., object] | None = None,
    ) -> None:
        if not isinstance(base_url, str):
            raise ValueError("Home Assistant base URL is invalid")
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("Home Assistant base URL must be one fixed origin")
        if parsed.scheme == "http" and not _is_loopback_host(parsed.hostname):
            raise ValueError("Home Assistant bearer tokens require HTTPS except on loopback")
        if (
            not isinstance(access_token, str)
            or len(access_token) < 20
            or len(access_token) > 4096
            or access_token.strip() != access_token
            or any(ord(character) < 33 or ord(character) == 127 for character in access_token)
        ):
            raise ValueError("Home Assistant access token is invalid")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not 0 < timeout_seconds <= 30:
            raise ValueError("Home Assistant timeout must be between 0 and 30 seconds")
        self._scheme = parsed.scheme
        self._host = parsed.hostname
        self._port = parsed.port or (443 if parsed.scheme == "https" else 80)
        self._token = access_token
        self._timeout = float(timeout_seconds)
        self._ssl_context = ssl_context
        self._connection_factory = connection_factory

    def get(self, path: str) -> HomeAssistantHttpResponse:
        if not self._allowed_path(path):
            raise HomeAssistantProtocolError("Home Assistant read path is not allow-listed")
        connection = self._open_connection()
        try:
            connection.request(
                "GET",
                path,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/json",
                },
            )
            response = connection.getresponse()
            body = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(body) > _MAX_RESPONSE_BYTES:
                raise HomeAssistantProtocolError("Home Assistant response exceeded the size limit")
            return HomeAssistantHttpResponse(
                status_code=response.status,
                content_type=response.getheader("Content-Type", ""),
                body=body,
            )
        except HomeAssistantAdapterError:
            raise
        except (OSError, http.client.HTTPException, TimeoutError):
            raise HomeAssistantUnavailableError("Home Assistant request failed") from None
        finally:
            try:
                connection.close()
            except Exception:
                pass

    @staticmethod
    def _allowed_path(path: object) -> bool:
        return isinstance(path, str) and (
            path in {"/api/", "/api/states"} or _STATE_PATH.fullmatch(path) is not None
        )

    def _open_connection(self):
        if self._connection_factory is not None:
            return self._connection_factory(
                self._scheme,
                self._host,
                self._port,
                self._timeout,
                self._ssl_context,
            )
        if self._scheme == "https":
            return http.client.HTTPSConnection(
                self._host,
                self._port,
                timeout=self._timeout,
                context=self._ssl_context,
            )
        return http.client.HTTPConnection(self._host, self._port, timeout=self._timeout)


@dataclass(frozen=True)
class HomeAssistantEntityState:
    entity_id: str
    state: str
    last_changed: str | None
    friendly_name: str | None
    device_class: str | None
    unit_of_measurement: str | None


class HomeAssistantReadClient:
    """Parse only bounded state metadata required by HearthGhost."""

    def __init__(self, transport: HomeAssistantReadTransport) -> None:
        if not callable(getattr(transport, "get", None)):
            raise TypeError("Home Assistant transport must expose get")
        self._transport = transport

    def ping(self) -> bool:
        response = self._transport.get("/api/")
        if response.status_code != 200:
            return False
        payload = self._json(response)
        return isinstance(payload, Mapping) and payload.get("message") == "API running."

    def list_states(self) -> tuple[HomeAssistantEntityState, ...]:
        response = self._transport.get("/api/states")
        if response.status_code != 200:
            raise HomeAssistantProtocolError("Home Assistant state list was unavailable")
        payload = self._json(response)
        if not isinstance(payload, list) or len(payload) > _MAX_ENTITIES:
            raise HomeAssistantProtocolError("Home Assistant state list is malformed")
        return tuple(self._parse_state(item) for item in payload)

    def get_state(self, entity_id: str) -> HomeAssistantEntityState:
        if not isinstance(entity_id, str) or _ENTITY_ID.fullmatch(entity_id) is None:
            raise ValueError("Home Assistant entity_id is invalid")
        response = self._transport.get(f"/api/states/{entity_id}")
        if response.status_code == 404:
            raise HomeAssistantProtocolError("Home Assistant entity was not found")
        if response.status_code != 200:
            raise HomeAssistantProtocolError("Home Assistant entity state was unavailable")
        state = self._parse_state(self._json(response))
        if state.entity_id != entity_id:
            raise HomeAssistantProtocolError("Home Assistant returned the wrong entity")
        return state

    def discover_supported_devices(self) -> tuple[DeviceObservation, ...]:
        observations: list[DeviceObservation] = []
        for state in self.list_states():
            capabilities = self._read_capabilities(state)
            if not capabilities:
                continue
            observations.append(
                DeviceObservation(
                    adapter_id="homeassistant",
                    external_id=state.entity_id,
                    display_name=state.friendly_name or state.entity_id,
                    area_id=None,
                    advertised_capabilities=capabilities,
                )
            )
        return tuple(observations)

    @staticmethod
    def _read_capabilities(state: HomeAssistantEntityState) -> frozenset[str]:
        domain = state.entity_id.partition(".")[0]
        capabilities = {"home.entity.read"}
        if domain == "light":
            capabilities.add("home.light.read")
        elif domain == "sensor" and state.device_class == "temperature":
            capabilities.add("sensor.temperature.read")
        elif domain == "sensor" and state.device_class == "humidity":
            capabilities.add("sensor.humidity.read")
        else:
            return frozenset()
        return frozenset(capabilities)

    @staticmethod
    def _json(response: HomeAssistantHttpResponse) -> object:
        if "json" not in response.content_type.lower():
            raise HomeAssistantProtocolError("Home Assistant returned a non-JSON response")
        try:
            return json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise HomeAssistantProtocolError("Home Assistant returned invalid JSON") from None

    @staticmethod
    def _parse_state(value: object) -> HomeAssistantEntityState:
        if not isinstance(value, Mapping):
            raise HomeAssistantProtocolError("Home Assistant state is not an object")
        entity_id = value.get("entity_id")
        state = value.get("state")
        attributes = value.get("attributes", {})
        last_changed = value.get("last_changed")
        if (
            not isinstance(entity_id, str)
            or _ENTITY_ID.fullmatch(entity_id) is None
            or not isinstance(state, str)
            or len(state) > 1024
            or not isinstance(attributes, Mapping)
            or len(attributes) > 256
            or (last_changed is not None and (not isinstance(last_changed, str) or len(last_changed) > 128))
        ):
            raise HomeAssistantProtocolError("Home Assistant state is malformed")

        def bounded_attribute(name: str, maximum: int) -> str | None:
            candidate = attributes.get(name)
            if candidate is None:
                return None
            if not isinstance(candidate, str) or len(candidate) > maximum:
                return None
            return candidate

        return HomeAssistantEntityState(
            entity_id=entity_id,
            state=state,
            last_changed=last_changed,
            friendly_name=bounded_attribute("friendly_name", 128),
            device_class=bounded_attribute("device_class", 64),
            unit_of_measurement=bounded_attribute("unit_of_measurement", 64),
        )


def home_assistant_read_capability_definitions() -> tuple[CapabilityDefinition, ...]:
    return (
        CapabilityDefinition("home.entity.read", "Read approved Home Assistant entity state.", ToolEffect.EXTERNAL_READ),
        CapabilityDefinition("home.light.read", "Read approved Home Assistant light state.", ToolEffect.EXTERNAL_READ),
        CapabilityDefinition("sensor.temperature.read", "Read approved temperature sensor state.", ToolEffect.EXTERNAL_READ),
        CapabilityDefinition("sensor.humidity.read", "Read approved humidity sensor state.", ToolEffect.EXTERNAL_READ),
    )


def home_assistant_entity_read_tool_definition() -> ToolDefinition:
    return ToolDefinition(
        name="home.entity.read",
        description="Read the current state of one explicitly approved Home Assistant entity.",
        effect=ToolEffect.EXTERNAL_READ,
        risk_level=ToolRiskLevel.LOW,
        required_context=ToolRequiredContext.EXPLICIT_USER_REQUEST,
        required_roles=frozenset({ActorRole.ADMINISTRATOR, ActorRole.HOUSEHOLD_MEMBER}),
        confirmation_policy=ConfirmationPolicy.NONE,
        audit_level=AuditLevel.METADATA,
        arguments_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["device_id"],
            "properties": {"device_id": {"type": "string", "minLength": 1, "maxLength": 128}},
        },
        allowed_capabilities=frozenset({"home.entity.read"}),
    )


class HomeAssistantEntityReadToolAdapter:
    """Policy-executed read adapter that rechecks current Registry trust."""

    def __init__(self, client: HomeAssistantReadClient, devices: SmartHomeDeviceRegistry) -> None:
        if not isinstance(client, HomeAssistantReadClient):
            raise TypeError("client must be a HomeAssistantReadClient")
        if not isinstance(devices, SmartHomeDeviceRegistry):
            raise TypeError("devices must be a SmartHomeDeviceRegistry")
        self._client = client
        self._devices = devices

    def execute(self, definition: ToolDefinition, proposal: ToolProposal) -> ToolAdapterResult:
        if definition.name != "home.entity.read" or proposal.tool_name != definition.name:
            return ToolAdapterResult(False, "adapter_tool_mismatch")
        device_id = proposal.arguments.get("device_id")
        if not isinstance(device_id, str):
            return ToolAdapterResult(False, "device_id_invalid")
        record = self._devices.get(device_id)
        if (
            record is None
            or record.trust_state is not DeviceTrustState.TRUSTED
            or record.adapter_id != "homeassistant"
            or "home.entity.read" not in record.approved_capabilities
        ):
            return ToolAdapterResult(False, "device_not_currently_authorized")
        try:
            state = self._client.get_state(record.external_id)
        except HomeAssistantAdapterError:
            return ToolAdapterResult(False, "home_assistant_read_failed")
        output: dict[str, object] = {
            "entity_id": state.entity_id,
            "state": state.state,
        }
        if state.friendly_name is not None:
            output["friendly_name"] = state.friendly_name
        if state.unit_of_measurement is not None:
            output["unit_of_measurement"] = state.unit_of_measurement
        if state.last_changed is not None:
            output["last_changed"] = state.last_changed
        return ToolAdapterResult(True, "home_assistant_state_read", MappingProxyType(output))
