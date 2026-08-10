# Infrastructure

This directory owns deployment and local infrastructure guidance for HearthGhost.

The repository-root `Dockerfile`, `compose.yaml`, and `.dockerignore` define the
HG-DEV-001 development/test boundary. They are validation infrastructure, not a
production deployment. The test image copies only the restricted build context,
runs as a non-root user, exposes no ports, and needs no persistent state.

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

Run the reproducible suite from the repository root with:

```text
docker compose build --pull test
docker compose run --rm test
```

Do not add privileged mode, host networking, Docker socket mounts, host device
passthrough, broad host mounts, or production secrets for development
convenience.

See:

- `../docs/security/trust-boundaries.md`
- `../docs/security/threat-model.md`
- `../docs/architecture/overview.md`
