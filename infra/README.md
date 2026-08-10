# Infrastructure

This directory will contain deployment and local infrastructure definitions for HearthGhost.

Initial target:

```text
Single Linux home server
WTR PRO
AMD Ryzen 7 5825U
GPU not assumed
```

Expected areas may include:

- container/runtime definitions
- reverse proxy and TLS
- network segmentation guidance
- MQTT if required
- Home Assistant integration/deployment notes
- secret-loading mechanisms
- backup and restore procedures
- observability and security audit support

Infrastructure must preserve the security model:

- no public port forwarding required for normal operation
- deny-by-default network posture
- controlled Internet egress
- no universal shared credentials
- no secrets committed to Git
- no `host` networking by default for convenience

Do not introduce Kubernetes or distributed infrastructure without a concrete need and documented decision.

See:

- `../docs/security/trust-boundaries.md`
- `../docs/security/threat-model.md`
- `../docs/architecture/overview.md`
