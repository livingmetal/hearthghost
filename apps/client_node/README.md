# Development Text Client Node

This test/development client represents the native secure-transport adapter
behind the HG-007 web client port. It reuses `MockNode`'s outbound mTLS and Node
Gateway session implementation, then sends versioned conversation commands on
the same TLS channel. Every command is independently admitted for
`conversation.text` by Node Gateway.

It owns no inbound listener, Android permission, camera, microphone, provider
credential, Policy decision, Tool executor, Home Assistant client, or physical
device integration. Production Android credential storage and transport remain
deferred behind the platform port from ADR-0005.
