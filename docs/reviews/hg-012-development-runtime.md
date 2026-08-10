# HG-012 development runtime review

## Result

Accepted for development use on WTR PRO. This is not a production deployment
or production PKI.

## Source baseline

- source branch: `codex/hg-011-text-walking-skeleton`
- source commit: `3a7d90452910ff5288a178837973da3428f8b89b`
- pre-change tests: 143 Python and 18 client tests passed in rebuilt rootless
  Podman images

## Implemented boundary

- ADR-0006 records the new inbound listener decision.
- `hearthghost-development-core` runs rootless as the unprivileged image user.
- application bind: `10.89.0.10:8443` on internal `10.89.0.0/24` network
- sole host publication: `192.168.55.100:38443`
- status bind: `127.0.0.1:8080` inside the container, not published
- TLS profile: TLS 1.3 only, required client certificate, ALPN
  `hearthghost-node/1`, no session tickets
- root filesystem read-only, all capabilities dropped, no-new-privileges,
  bounded PID/memory/CPU, no devices, host mode, Podman socket, or broad mount
- fake LLM selected in-process; internal network has no default route and no
  provider credential is mounted

## PKI and state

- user-scoped files live under
  `/home/kaiser/.local/share/hearthghost-development`
- authority key and runtime state are mode 0600; containing directories are
  mode 0700
- the authority key is not mounted into Core or the administration container
- Node signing requires a separately generated CSR, inspection, and an exact
  administrator-approved SHA-256 fingerprint
- only the public certificate fingerprint is bound to credential and Node IDs
- advertisement, enrollment, trust, grant, capability revocation, Node
  revocation, and credential revocation remain distinct operations
- persistent credential and registry state is re-read on protected requests;
  session/replay/conversation state remains ephemeral

## Verification evidence

- post-change Python suite: 148 tests passed
- client suite: 18 tests passed
- deployment health: healthy after rootless container rebuild
- `/proc/net/tcp` showed listeners only at `10.89.0.10:8443` and
  `127.0.0.1:8080`
- host socket inspection showed only `192.168.55.100:38443` for the Gateway
- a TLS 1.3/ALPN client without a client certificate received the expected
  `certificate required` alert
- administration probe completed advertise, enroll, trust, grant,
  revoke-capability, and revoke-Node, ending at revision 5 with no grant and
  `revoked` trust state
- restart retained the persistent state while invalidating process-local
  sessions
- diff, container-definition, and secret-pattern scans found no credential,
  private key, generated certificate, cache, or build artifact in Git

## Deferred

- Android Keystore key generation and CSR creation
- Android certificate-chain installation and native-owned mTLS
- provider egress/secret isolation and live Luna conversation
- physical phone validation
