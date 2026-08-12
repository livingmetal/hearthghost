# ADR-0009: Opt-in validated Windows development update channel

## Status

Accepted

## Context

The Windows development Node is installed separately from its Git worktree.
Pulling a remote branch therefore does not update the running web assets or the
published native shell. Manually copying individual files is error-prone,
especially when package locks, pinned presentation assets, or native code
change together.

An updater also creates a software-supply-chain boundary: fetching a branch and
executing its build scripts must not silently become an unrestricted
"latest branch" installer, expose local secrets to child processes, replace a
signed binary with an unsigned one, or destroy the last known-good install.

## Decision

Provide an opt-in development launcher with an explicitly configured local Git
source and one explicitly configured `origin` branch. On startup it:

1. fetches only the exact configured branch ref;
2. resolves the remote commit and compares it with the installed marker;
3. checks out that commit in a detached temporary worktree;
4. removes common secret-bearing environment variables from build children;
5. recreates locked dependencies and runs all packaged client tests;
6. fetches and hash-verifies the pinned local presentation assets;
7. builds the web client and publishes the native Windows client;
8. preserves the existing native signer when the installed executable is
   signed, and verifies the new signature;
9. swaps the candidate into place only after all validation succeeds; and
10. retains and automatically restores the prior installation if startup fails.

The launcher never infers the newest branch, changes the developer's active
worktree, runs `git pull`, copies credentials, or obtains provider secrets. A
channel advance is an explicit update of the configured branch name.

This is a development convenience, not a production software-update protocol.

## Consequences

Normal launches perform a lightweight fetch and commit comparison. A new
commit makes the first launch slower because tests, asset verification, package
installation, native publication, and signing run before the UI opens. Failed
validation leaves the currently installed build untouched and reports a local
status without preventing the prior build from starting.

One previous installation consumes additional disk space. Temporary build
dependencies are recreated rather than copied from another workstation.

## Alternatives considered

### Follow the newest remote branch automatically

Rejected. Branch recency is not approval and would let an unrelated pushed
branch become executable on the Node.

### Pull and run directly in the developer's active worktree

Rejected. It could overwrite or depend on local state, mix generated assets
with source changes, and leave the only runnable installation partially built.

### Download GitHub Actions artifacts

Deferred. A production-quality release channel should eventually use signed,
versioned artifacts and a release manifest, but the repository does not yet
publish a durable Windows release artifact.

## Security / Privacy impact

The explicitly configured Git remote branch remains a trusted development
software source and can execute package/build code inside the user's account.
The detached worktree, secret-stripped build environment, credential-free
origin requirement, exact refspec, signature continuity, and retained rollback
reduce but do not eliminate supply-chain risk.

Node private keys remain in the Windows certificate store. The updater handles
only public certificate thumbprints and requests Authenticode signing through
the existing non-exported private key. Provider credentials remain server-side
and are not required by update, build, test, or client startup.
