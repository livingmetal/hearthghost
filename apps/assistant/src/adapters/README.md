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
