# Adapters

Provider- and product-specific implementations live here behind ports. Future
families may include LLM, STT, TTS, Home Assistant, vision, and robot adapters.

No provider is selected in HG-001. Adapters may not leak credentials or provider
payloads into domain contracts, and cloud-bound content must pass through the
Privacy Gateway.

`node_tls_transport.py` is the HG-004 standard-library TLS 1.3 adapter for
already-connected Node sockets. It requires mutual certificate authentication
and the HearthGhost Node ALPN profile, then supplies only the verified public
certificate to the credential identity resolver. It creates no listener and
does not turn transport authentication into Node trust or action authorization.

`in_memory_core.py` provides volatile, lock-protected registry, credential,
session, replay, and deny-only identity adapters for HG-005. They are executable
development/runtime composition pieces, not production persistence or identity
providers. `contract_catalog.py` loads only schema identity/version metadata and
does not pretend to perform full JSON Schema validation.

`node_gateway_protocol.py` implements bounded v1.0 framing after mutual TLS. It
rejects unknown message fields and dispatches only session open/close and
sequenced capability admission. It owns no listener and an accepted result
remains narrower than Policy or execution.

`fake_llm.py` is the explicitly selected offline adapter. `openai_responses.py`
is the server-only Responses API adapter; construction is side-effect-free and
live calls require explicit OpenAI selection plus server-side secret injection.
Neither adapter has Tool or device execution access.
