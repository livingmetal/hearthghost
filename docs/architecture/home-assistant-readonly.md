# Read-only Home Assistant Adapter

HG-055 introduces the first Home Assistant integration boundary, deliberately limited to state reads.

The implementation follows the Home Assistant REST API shape documented at `https://developers.home-assistant.io/docs/api/rest/`:

- `GET /api/` for API health
- `GET /api/states` for state discovery
- `GET /api/states/<entity_id>` for one entity state
- bearer-token authorization owned by the adapter

## Hard read-only boundary

`HomeAssistantRestReadTransport` has only `get()` and accepts only these paths:

```text
/api/
/api/states
/api/states/<validated entity_id>
```

It rejects every other path, including:

```text
/api/services/...
/api/camera_proxy/...
/api/template
/api/events/...
```

There is no POST method and no arbitrary URL method.

This is intentional. Home Assistant service calls can communicate with real devices and belong behind a later write/physical-action Tool and confirmation policy.

## Credential handling

The bearer token is constructor-owned private adapter state. It is not part of:

- an LLM request or response,
- Tool Proposal arguments,
- Tool Registry metadata,
- Device Registry records,
- Tool Adapter results.

The transport does not follow redirects because it uses an exact configured origin. This prevents an Authorization header from being redirected to another host.

HTTPS is required for non-loopback origins. Plain HTTP is permitted only for literal loopback/localhost development where the token does not traverse the LAN.

A deployment using an internal CA may inject a reviewed `ssl.SSLContext` rather than disabling certificate verification.

## Bounded state parsing

The adapter limits response size and entity count, validates entity IDs, requires JSON, and extracts only state metadata needed by HearthGhost:

- entity ID
- state
- last-changed timestamp
- friendly name
- device class
- unit of measurement

Arbitrary Home Assistant attributes are not forwarded into Tool results.

## Discovery scope

HG-055 discovers only selected state-only domains:

```text
light.*                  -> home.entity.read + home.light.read
sensor.* temperature     -> home.entity.read + sensor.temperature.read
sensor.* humidity        -> home.entity.read + sensor.humidity.read
```

Camera entities are intentionally ignored. Switches and other actuator domains are also ignored until their risk model is reviewed.

Discovery still follows HG-054 rules: every observation starts untrusted and receives zero approved capabilities.

## End-to-end state read

The first Tool is `home.entity.read`.

It requires:

- an explicit user request,
- administrator or household-member role,
- a trusted Smart Home Device Registry record,
- explicit approval of `home.entity.read` for that device,
- an HG-053 Policy allow decision,
- a fresh non-replayed decision accepted by `GuardedToolExecutor`.

The adapter rechecks current Registry trust and capability immediately before the HTTP GET. If the device is revoked after Policy evaluation but before execution, the GET is not made.

## Deliberately absent

HG-055 does not implement:

- Home Assistant service calls
- light on/off writes
- lock/door controls
- camera snapshots or streams
- templates
- arbitrary HA event firing
- Home Assistant administration
- token creation/rotation UI
- automatic device trust

The next safe expansion is persistent Device Registry/audit state and deployment-secret wiring, followed by one narrowly reviewed low-risk write capability.
