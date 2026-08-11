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

## Optional PostgreSQL persistence

The runtime keeps file-backed development storage unless the operator explicitly
selects an existing rootless Podman secret. Create the secret outside the
repository without placing the DSN on a command line, then deploy with only its
public secret name:

```text
podman secret create hearthghost-postgres-dsn /secure/operator/path/postgres-dsn
HEARTHGHOST_POSTGRES_SECRET_NAME=hearthghost-postgres-dsn \
  deploy/development/hearthghost-development.sh deploy
```

The DSN file must contain one `postgresql://...?...sslmode=require` line for the
dedicated unprivileged HearthGhost role. The script rejects invalid or missing
secret names, mounts the selected secret read-only at
`/run/secrets/hearthghost-postgres-dsn`, and passes only that mounted path to the
Core. The DSN is never put in Git, an image, a build argument, or an environment
value. The PostgreSQL container must be attached to the internal development
network separately; do not make that network non-internal merely to reach the
database.

## Explicit conversation principal binding

Memory, notes, todos and behavior preferences fail closed until an administrator
binds a Node to one exact user or household scope. Select one development
binding explicitly when deploying; the script has no permissive default and
does not infer scope from an authenticated Node:

```text
HEARTHGHOST_POSTGRES_SECRET_NAME=hearthghost-postgres-dsn \
HEARTHGHOST_MEMORY_PRINCIPAL_BINDING=windows-development-01=user:windows-development-user \
  deploy/development/hearthghost-development.sh deploy
```

The binding contains no credential, but it is an authorization decision. Use a
separate Node ID and reviewed binding for every additional laptop or phone. The
value is passed as the existing `--memory-principal NODE_ID=SCOPE:SCOPE_ID`
runtime argument and is never converted into a Node trust or capability grant.

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
