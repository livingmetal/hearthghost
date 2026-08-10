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

For container runtimes, `OPENAI_API_KEY_FILE` may instead name a regular,
read-only server secret file. Configuring both key sources is rejected as
ambiguous. The adapter reads at most 16 KiB of key material and requests at most
1,024 output tokens. Neither setting changes the default Core composition or
the network-isolated test suite.

## Opt-in provider smoke test

The `openai-smoke` image performs exactly one synthetic text request through the
real Privacy Gateway and LLM Port. It requires explicit `--adapter openai`
selection, defaults specifically to the cost-oriented `gpt-5.6-luna` model,
reports only status metadata and response length, and exposes no Tool executor.
It is not part of normal tests and must never receive household conversation
content. This smoke-only choice does not change the adapter's normal Core
default and can still be overridden explicitly with `OPENAI_MODEL`.

With the external `hearthghost-openai-api-key` secret already present, a Compose
provider can run the opt-in profile:

```text
docker compose --profile provider-smoke build openai-smoke
docker compose --profile provider-smoke run --rm openai-smoke
```

Rootless Podman can run the same repository-defined image directly:

```text
podman build --pull=never --target openai-smoke \
  -t hearthghost-openai-smoke:local .
podman run --rm \
  --network podman \
  --read-only \
  --tmpfs /tmp:size=16m,mode=1777 \
  --cap-drop all \
  --security-opt no-new-privileges \
  --secret source=hearthghost-openai-api-key,type=mount,target=openai-api-key,uid=10001,gid=10001,mode=0400 \
  --env OPENAI_API_KEY_FILE=/run/secrets/openai-api-key \
  --env OPENAI_MODEL=gpt-5.6-luna \
  hearthghost-openai-smoke:local
```

This one-off container has outbound networking because the provider call
requires it, but publishes no port and mounts no repository or host directory.
Normal Core, fake walking-skeleton, Python tests, and client tests retain
`network_mode: none`.

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
