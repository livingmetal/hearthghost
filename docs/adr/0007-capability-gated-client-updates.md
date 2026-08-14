# ADR-0007: Capability-gated Windows client updates

## Status

Accepted

## Context

The installed Windows client should follow a reviewed server deployment without requiring a separate manual client copy on every release. Treating an authenticated Node as automatically authorized to download executable code would collapse identity and capability boundaries. A public download endpoint would also add an unnecessary listener.

## Decision

The development Core image builds one `win-x64` client bundle from the same Git commit and exposes it only through the existing TLS 1.3 mutual-authentication listener. Every update check and every file request consumes a Node replay sequence and is admitted independently through the exact `client.update` capability.

The authenticated manifest binds the Git commit release ID, relative path, byte length and SHA-256 for every file. The client downloads into a user-scoped staging directory, rejects traversal, size excess, truncation and hash mismatch, then launches the staged verified executable as a helper. After the old process exits, the helper swaps the installation directory and retains one previous directory for recovery. Update failure leaves the current client in place and does not weaken certificate validation.

The bundle contains the built web UI, so the installed client maps static files into WebView2 through a private virtual host and does not require a separately managed Vite process.

## Consequences

- Deploying a new Git commit builds both Core and the corresponding Windows bundle.
- A Node administrator must separately advertise and grant `client.update`.
- No new host port, CA trust-store elevation, bearer credential or provider secret is introduced.
- The current installation needs one final bootstrap replacement before it can self-update.
- Authenticode signing and multi-channel rollout policy remain deferred; transport authenticity currently comes from the pinned private CA plus the hash-bound mTLS manifest.

## Alternatives considered

- GitHub release polling was rejected because it bypasses the private Node authorization boundary and requires public Internet access from the client.
- A public LAN HTTP endpoint was rejected because it adds a listener and weakens identity-specific authorization.
- Shipping generated binaries in Git was rejected because release artifacts would obscure source review and inflate repository history.

## Security / Privacy impact

Authenticated Node is not update-authorized Node. Revocation, trust, capability admission and replay checks remain fail closed for each request. Only application files are distributed; credentials, private keys, household data, provider secrets and server state are absent from the bundle.
