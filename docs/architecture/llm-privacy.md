# LLM and Privacy Gateway

HG-010 introduces a text-only provider boundary:

```text
Conversation Turn
  -> Orchestrator
  -> Privacy Gateway
  -> LLM Port
  -> explicitly selected adapter
```

The default cloud policy allows text and denies audio, image, and video. The
Privacy Gateway is the only route from orchestration to an LLM adapter. Provider
failure, timeout, malformed output, or an unavailable adapter produces a typed
failure and safe user-facing text.

`FakeLLMAdapter` is deterministic and must be explicitly selected by a
development/test composition. The normal Core composition uses a provider-
unavailable adapter; it does not silently fall back to fake or network access.

`OpenAIResponsesAdapter` is server-only and calls the Responses API with text
`instructions` and `input`, `store: false`, a bounded response, and an explicit
timeout. It scans all assistant message output items rather than assuming text
is the first output item. `OPENAI_API_KEY` and optional `OPENAI_MODEL` are read
only when OpenAI is explicitly selected. A missing key fails during adapter
configuration. Credentials are never logged, copied into the web/Android
client, embedded in an image, or accepted as a build argument.

The official OpenAI text guide documents `POST /v1/responses`, bearer
authentication, `model`, `instructions`, `input`, and the multi-item `output`
shape. OpenAI's production guidance recommends environment variables or a
secret manager instead of source or public repositories:

- <https://developers.openai.com/api/docs/guides/text>
- <https://developers.openai.com/api/docs/guides/production-best-practices>

An LLM completion may contain a typed proposed action with
`authorization_status=pending_policy`. No executor is reachable through the LLM
port, Privacy Gateway, or orchestrator. HG-010 performs no Home Assistant or
physical-device call.
