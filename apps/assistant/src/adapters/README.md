# Adapters

Provider- and product-specific implementations live here behind ports. Future
families may include LLM, STT, TTS, Home Assistant, vision, and robot adapters.

No provider is selected in HG-001. Adapters may not leak credentials or provider
payloads into domain contracts, and cloud-bound content must pass through the
Privacy Gateway.
