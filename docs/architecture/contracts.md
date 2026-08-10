# Contracts and Transport

## Principle

Cross-module and cross-device communication should use explicit, semantic, versionable contracts. Internal components must not exchange arbitrary provider-specific payloads as if they were domain contracts.

Important contract families include:

- node identity and registration
- node capabilities
- attention and conversation state
- character state and emotion
- speech events
- tool definitions and proposals
- policy decisions
- device state
- behavior-preference updates
- audit events

## Semantic events

Prefer domain meaning over renderer or vendor implementation detail.

Example:

```json
{
  "type": "character.state",
  "version": 1,
  "request_id": "abc123",
  "payload": {
    "state": "thinking",
    "emotion": "curious"
  }
}
```

Example tool proposal:

```json
{
  "type": "tool.proposal",
  "version": 1,
  "request_id": "abc123",
  "payload": {
    "name": "home.light.set",
    "arguments": {
      "area": "livingroom",
      "brightness": 50
    }
  }
}
```

The tool proposal is not permission to execute. Policy and authorization still apply.

## Transport direction

The exact transport stack may evolve, but the initial architecture should support:

```text
WebSocket or equivalent long-lived authenticated channel
  -> states, commands, events, session coordination

HTTPS / binary transfer / binary WebSocket frames
  -> audio, snapshots, larger payloads when needed
```

Do not encode large audio or image payloads as Base64 JSON by default when a binary transport is more appropriate.

## Security

Transport encryption does not replace authorization. An authenticated node still receives only the capabilities and actions allowed by policy.

Future node authentication should support per-node revocable credentials and strong mutual identity verification.

Node identity and capability v2 plus the Node credential lifecycle contract
deliberately keep logical trust, credential validity, advertised capabilities,
and grants separate. Node Gateway replay admission uses a technical session
identifier and monotonically increasing per-session sequence in domain code;
HG-006 adds a bounded length-prefixed JSON v1.0 frame for technical session
open/close and sequenced capability requests. It does not define media transport
or a network listener.

HG-011 adds a separate conversation command/result v1 family without changing
the immutable Node Gateway v1 contract. Conversation frames use the same
bounded framing and connected mTLS channel. Every open, text, or close command
contains the Node technical session and a monotonically increasing sequence;
the server passes that command through Node Gateway for the exact
`conversation.text` capability before dispatch. A conversation result contains
only text, validated semantic character-state events, and proposals explicitly
marked `pending_policy` / `not_executed`. Provider payloads and secrets are not
wire fields.

Node administration command/result v1 represents explicit registry mutation.
Its operation ID provides idempotency and its expected revision prevents stale
updates. Administrator identity comes from the authenticated administration
boundary rather than caller-supplied contract fields. An applied administration
result is not a Policy Decision or execution authorization.

## Versioning

Public event and tool schemas should carry a version. Breaking changes require coordinated schema, test, and documentation updates.

Do not casually expose provider response objects as stable public contracts.

## Contract ownership

The contract layer owns shared schemas. Individual adapters translate between external/vendor schemas and HearthGhost contracts.

```text
Vendor / Provider schema
        |
      Adapter
        |
HearthGhost Contract
        |
       Core
```
