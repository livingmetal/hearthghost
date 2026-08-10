# HG-011 Text Walking Skeleton Review

## Scope

HG-011 connects the smallest text-only slice without adding a listener, media,
physical execution, production PKI, or a live provider call.

```text
Development Client Node
  -> ephemeral mTLS socket pair
  -> Node technical session
  -> per-command replay + trust + conversation.text grant admission
  -> bounded Conversation Session
  -> Orchestrator
  -> Privacy Gateway
  -> explicitly selected FakeLLMAdapter
  -> text + semantic character states + inert proposals
  -> strict client result parser / CharacterViewport contract
```

The Python development Client Node represents the future native platform
adapter behind the TypeScript client port. It uses the same TLS, certificate
resolution, Node Gateway, session, replay, trust, and grant implementation as
the HG-006 Mock Node. Platform-specific Android Keystore and lifecycle code is
still deferred.

## Security review

- Unknown, untrusted, revoked, or ungranted clients are denied by Node Gateway.
- Every conversation command consumes the technical session's monotonic replay
  sequence before trust and grant evaluation.
- Conversation IDs and lifetimes are independent of Node technical sessions.
- Conversation timeout/end does not revoke identity or close the Node session.
- The default Privacy Gateway policy allows text and denies audio/image/video.
- The fake adapter is explicitly injected; default Core remains provider-
  unavailable and does not silently use fake or OpenAI.
- Provider credentials are server-only. No client, schema, container argument,
  or image environment contains an API key.
- Proposed actions are transported only as `pending_policy` and
  `not_executed`. No executor or Home Assistant adapter exists in this slice.
- Renderer-specific states, unknown result fields, secret-bearing fields,
  plaintext protocol use, malformed frames, and replay fail closed.
- Test certificates are generated in a temporary directory and removed. No
  production CA or certificate is created.

## Acceptance evidence

The E2E scenario establishes a trusted Client Node, opens a separate text
conversation, processes Korean ordinary conversation through Privacy Gateway
and the fake LLM, emits listening/thinking/speaking/engaged states, stays engaged
for follow-up, returns a light-off proposal as unavailable and unexecuted, then
ends the conversation while the Node technical session remains connected.

The repository-defined `walking-skeleton` image runs only that integration
scenario under a non-root user with no network, read-only root filesystem,
dropped capabilities, `no-new-privileges`, and tmpfs for ephemeral certificates.

## Post-milestone provider validation

On 2026-08-11, the dedicated `openai-smoke` image completed one synthetic
text-only request through the real Privacy Gateway, LLM Port, and
`OpenAIResponsesAdapter` using the `gpt-5.6` alias. A rootless external Podman
secret was mounted read-only; no credential, prompt, or provider response body
was printed. The process reported only `status=ok`, `modality=text`, and a
31-character response length.

This validation remains separate from the normal suite. The Python and client
test containers keep networking disabled and require no provider credential.
The same synthetic check subsequently passed with an explicit
`gpt-5.6-luna` selection and a 31-character response; Luna is now the dedicated
smoke path's default while the normal adapter default remains unchanged.

## Deferred

- production provider routing, rate/cost budgets, retries, and network-layer
  egress allowlisting;
- representative conversation quality, latency, and provider evaluation;
- Android native Keystore/mTLS bridge and device lifecycle validation;
- persistent conversation/session storage and behavior-preference persistence;
- representative Android VRM performance and an approved character asset;
- production listener, connection limits, rate limiting, and deployment;
- Voice, STT/TTS, microphone/camera, cloud media, Home Assistant execution, and
  all physical-device control.
