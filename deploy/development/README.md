# Rootless development runtime

HG-012 deploys one fake-LLM Core/Node Gateway as the unprivileged `kaiser`
account on WTR PRO. ADR-0006 defines the listener and persistence boundaries.

From the repository root on WTR PRO:

```text
chmod +x deploy/development/hearthghost-development.sh
deploy/development/hearthghost-development.sh deploy
deploy/development/hearthghost-development.sh status
```

The script creates only user-scoped files under
`~/.local/share/hearthghost-development` and rootless Podman objects. The CA
private key remains in `authority/` and is never mounted into the runtime. The
runtime exposes only `192.168.55.100:38443`; its status endpoint remains inside
the container on loopback. The internal network has no Internet route. No
OpenAI secret is mounted into this milestone.

## Remote Android development access

Do not expose TCP/38443 through a home-router port forward. ADR-0007 keeps the
HearthGhost Gateway private and places remote connectivity in a separate private
routing layer.

The preferred development layout is:

```text
HearthGhost Android client on mobile Internet
        |
        | Tailscale subnet route
        v
WTR PRO subnet router
        |
        | routed development subnet
        v
192.168.55.100:38443
        |
        | HearthGhost TLS 1.3 + per-node mTLS
        v
Node Gateway
```

This deliberately preserves the Android transport's fixed
`192.168.55.100:38443` endpoint and the server certificate bound to that IP.
Tailscale grants reachability only; it does not grant HearthGhost Node trust or
capabilities.

HearthGhost does not require a full-tunnel exit node. Keep ordinary phone
Internet traffic on its normal path. If a payment, banking, vehicle, projection,
or other application behaves incorrectly while Tailscale is connected, use the
Android Tailscale client's app-based split-tunneling setting to exclude that
application. Excluded application traffic and DNS bypass Tailscale; applications
not excluded can continue to reach the tailnet.

For a Tailscale-based development setup, configure the WTR PRO Linux host as a
subnet router for the smallest CIDR that contains the Gateway. Linux subnet
routing requires IP forwarding and uses:

```text
sudo tailscale set --advertise-routes=<development-subnet-cidr>
```

Approve the route in the tailnet control plane and restrict tailnet access so
only the designated Android test device or user can reach the development
route. Do not commit Tailscale auth keys or account-specific policy material to
this repository.

Before HG-014 enrollment:

1. connect Tailscale on the Android phone without selecting a home exit node;
2. add split-tunnel exclusions only for applications that demonstrate VPN
   compatibility problems;
3. verify excluded applications still work through ordinary mobile/Wi-Fi
   connectivity;
4. switch to mobile data and verify HearthGhost has route reachability to
   `192.168.55.100`;
5. do not weaken TLS, certificate validation, Node enrollment, trust, capability
   grants, or replay protection to compensate for a routing problem.

Android's user-facing Tailscale split-tunnel mode is exclusion-oriented. A
strict mode where only HearthGhost uses Tailscale is possible through Android
system policy/MDM, but is not required for the current personally managed test
phone.

## One Android Node credential

The Android app must generate its key in Android Keystore and export only a
CSR. Copy that CSR to the enrollment directory outside the repository, then
inspect it without signing:

```text
python -m apps.assistant.src.runtime.development_pki inspect-node-csr \
  --csr ~/.local/share/hearthghost-development/enrollment/android-development-01/node.csr
```

After the administrator compares the displayed SHA-256 fingerprint with the
device, sign only with an explicit matching value:

```text
python -m apps.assistant.src.runtime.development_pki sign-node-csr \
  --authority-dir ~/.local/share/hearthghost-development/authority \
  --csr ~/.local/share/hearthghost-development/enrollment/android-development-01/node.csr \
  --node-id android-development-01 \
  --approve-sha256 <exact-inspected-sha256> \
  --certificate-out ~/.local/share/hearthghost-development/enrollment/android-development-01/node.crt
```

Signing does not enroll, trust, or grant the Node. Those remain explicit local
CLI operations. Container paths below refer to the narrowly scoped, read-only
`/development-enrollment` mount; the authority directory is not mounted:

```text
deploy/development/hearthghost-development.sh admin provision-credential \
  --node-id android-development-01 \
  --credential-id android-development-credential-01 \
  --certificate /development-enrollment/android-development-01/node.crt
deploy/development/hearthghost-development.sh admin advertise \
  --node-id android-development-01 \
  --capability display \
  --capability conversation.text
deploy/development/hearthghost-development.sh admin enroll \
  --node-id android-development-01
deploy/development/hearthghost-development.sh admin trust \
  --node-id android-development-01 --state-value trusted
deploy/development/hearthghost-development.sh admin grant \
  --node-id android-development-01 --capability conversation.text
```

Revocation is similarly explicit and is observed by the running Gateway on the
next protected request:

```text
deploy/development/hearthghost-development.sh admin revoke-capability \
  --node-id android-development-01 --capability conversation.text
deploy/development/hearthghost-development.sh admin revoke-node \
  --node-id android-development-01
deploy/development/hearthghost-development.sh admin revoke-credential \
  --credential-id android-development-credential-01
```

Never place a Node private key, CA private key, provider key, generated
certificate, state file, or enrollment artifact in the repository.
