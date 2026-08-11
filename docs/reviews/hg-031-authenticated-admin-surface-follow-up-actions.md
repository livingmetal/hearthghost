# HG-031 Authenticated Administrator Surface Follow-up Actions

Status: implementation in progress. The existing HG-025 dashboard remains a separate read-only listener; this work adds a distinct authenticated write boundary.

## Security invariants

- [ ] Administrator listener binds to a literal loopback address only.
- [ ] Listener is disabled unless an explicit owner-only token secret file is configured.
- [ ] Token secret is loaded from a regular non-symlink file, is never accepted from CLI arguments, query strings, HTML, cookies, localStorage or sessionStorage, and is compared in constant time.
- [ ] Requests use `Authorization: Bearer ...`; token values never appear in logs or response bodies.
- [ ] No CORS is enabled; mutating responses use `Cache-Control: no-store`.
- [ ] JSON bodies are bounded and exact-field validated before reaching domain administration.
- [ ] Existing NodeAdministration remains the only path for enroll/trust/grant/revoke mutations.
- [ ] Expected revision and operation UUID remain mandatory for NodeAdministration mutations.
- [ ] Capability grant still requires an advertised capability.
- [ ] Capability advertisement replacement is a separate administrator operation with its own validation and audit event. It never grants the capability by itself.
- [ ] `notification.local` advertisements must require Node-local authorization.
- [ ] The administrator surface never changes Hard Policy, provider secrets, PostgreSQL credentials, Memory contents, conversation text, Android local permission, or tool execution authority.

## Capability advertisement operational gap

HG-030 requires `notification.local`, but the current Node protocol has no attested client advertisement message. Initial HG-031 support should therefore expose an explicit administrator-controlled advertisement registration operation for a known Node build. This is configuration, not a grant. A future attested Node capability-discovery protocol can replace it after a separate design review.

## Operator actions

- [ ] Generate a high-entropy administrator bearer token outside the repository and store it in a mode-0600 secret file.
- [ ] Keep the administrator API reachable only through local host access or an explicitly reviewed SSH/private administrative tunnel; do not port-forward it publicly.
- [ ] Enroll the Android Node, register advertisements for `conversation.text` and `notification.local` (`local_authorization_required=true` for the latter), set trust, then grant each capability deliberately using current revision values.
- [ ] Review audit event growth and establish an archival/retention policy before long-term production use.

## Physical end-to-end checks

- [ ] Verify an absent/wrong token returns 401 without revealing whether a Node exists.
- [ ] Verify stale revision returns a conflict and does not mutate Node state.
- [ ] Verify registering `notification.local` does not grant it.
- [ ] Verify grant fails before advertisement and succeeds after advertisement/trust with the correct revision.
- [ ] Verify a revoked Node cannot regain trust/grants through the API.
- [ ] Verify Android reminder sync remains denied until `notification.local` is both advertised and granted.

## Future UI gate

If a browser-based administrator write UI is added, the token must remain memory-only and be explicitly pasted for the current page lifetime. Do not introduce cookies or browser persistence merely for convenience. Keep the read-only dashboard usable without administrator credentials.
