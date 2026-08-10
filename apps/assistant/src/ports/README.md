# Ports

Ports define stable interfaces the domain needs from storage, external AI,
speech, node transport, devices, clocks, and audit sinks. Ports use HearthGhost
contracts and domain types, never provider response objects.

Security-sensitive ports must make authorization context explicit and must not
offer convenience methods that bypass Policy or Privacy Gateway evaluation.
