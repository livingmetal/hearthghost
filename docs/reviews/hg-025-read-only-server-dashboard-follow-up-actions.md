# HG-025 Read-only Server Dashboard Follow-up Actions

Status: local operator visibility only. This work does not add remote administration or any write authority.

## Implemented surface

- [x] Adds a standalone `AdminDashboardServer` rather than adding writes to the Core status API.
- [x] Dashboard accepts a literal loopback address only.
- [x] Development runtime keeps the dashboard disabled unless `--admin-dashboard-port PORT` is explicitly provided.
- [x] Development runtime hard-codes dashboard bind to `127.0.0.1`; there is no dashboard bind CLI option.
- [x] Dashboard and status port collision on `127.0.0.1` is rejected before service startup.
- [x] Dashboard renders only the already-sanitized `CoreComponents.status()` document.
- [x] GET is limited to static dashboard assets and `/api/status`.
- [x] POST, PUT, PATCH, and DELETE return HTTP 405.
- [x] Responses are `no-store` and include nosniff, frame denial, no-referrer, and restrictive CSP headers.
- [x] Browser rendering uses `textContent` / DOM nodes instead of injecting status values through `innerHTML`.
- [x] Dashboard JavaScript does not use localStorage/sessionStorage.
- [x] Dashboard does not expose PostgreSQL DSNs, provider credentials, Node private keys, raw memory, TODO text, reminder text, or notification payloads.

## Example development startup

The dashboard remains optional. When intentionally enabled, use a separate loopback port such as:

```text
--admin-dashboard-port 8081
```

The resulting operator surface is reachable only from the server host at `127.0.0.1:8081` unless an operator separately uses a reviewed authenticated access mechanism.

## Do NOT do this

- [ ] Do not change the dashboard bind to `0.0.0.0` merely to make it convenient remotely.
- [ ] Do not expose this unauthenticated dashboard directly over Tailscale as a substitute for an admin-authentication design.
- [ ] Do not add Node trust/grant/revoke writes to this read-only HTTP server.
- [ ] Do not add Policy writes or direct SQL consoles to this server.
- [ ] Do not return raw Memory/TODO/Reminder rows from the generic status endpoint.
- [ ] Do not place credentials, DSNs, private keys, bearer tokens, or provider configuration in HTML/JavaScript.

## Physical/operator validation

- [ ] Start the development server without `--admin-dashboard-port`; confirm no dashboard listener exists.
- [ ] Start with a valid dashboard port and confirm it listens only on `127.0.0.1`.
- [ ] Confirm `/`, `/admin`, CSS, JavaScript, and `/api/status` load correctly in a real browser.
- [ ] Confirm POST/PUT/PATCH/DELETE remain 405 using an external HTTP client.
- [ ] Confirm browser developer tools show the intended CSP and no-store headers.
- [ ] Confirm the rendered status contains no private Node identifiers or household content beyond the intentionally sanitized boundary names/states.
- [ ] Confirm process shutdown closes both the Core status listener and dashboard listener.

## Server dashboard product follow-up

- [ ] Add PostgreSQL health as a coarse state only; never expose the DSN.
- [ ] Add safe aggregate counters only after deciding whether counts themselves are sensitive in household deployments.
- [ ] Add Node inventory summary using public IDs/trust/capability metadata only after an authenticated administrator surface exists.
- [ ] Add Memory/TODO/Reminder counts separately from their private content.
- [ ] Add reminder delivery-attempt status after scheduler/delivery persistence exists.
- [ ] Add persona/behavior preference read-only state without exposing Hard Policy internals or prompt text.
- [ ] Add build/version/migration version fields for operator diagnostics.

## Future write/admin UI boundary

- [ ] Design explicit administrator authentication independently from Node-user conversation authentication.
- [ ] Use CSRF-resistant authenticated write APIs if a browser admin UI is introduced.
- [ ] Every Node enrollment/trust/grant/revoke operation must continue through `NodeAdministration` and its authorizer, never direct registry mutation from HTTP handlers.
- [ ] Principal bindings and notification routes require explicit administrator authorization and audit events.
- [ ] Behavior preference writes must remain separate from Hard Policy and secret/provider configuration.
- [ ] Remote admin access must use a reviewed private/authenticated mechanism; being on the Tailnet alone must not automatically mean administrator authority.
