#!/usr/bin/env bash
set -euo pipefail

IMAGE="localhost/hearthghost-development-core:local"
CONTAINER="hearthghost-development-core"
NETWORK="hearthghost-development-internal"
NETWORK_SUBNET="10.89.0.0/24"
CONTAINER_IP="10.89.0.10"
HOST_IP="192.168.55.100"
HOST_PORT="38443"
CONTAINER_PORT="8443"
DATA_ROOT="${XDG_DATA_HOME:-${HOME}/.local/share}/hearthghost-development"
AUTHORITY_DIR="${DATA_ROOT}/authority"
TLS_DIR="${DATA_ROOT}/runtime-tls"
STATE_DIR="${DATA_ROOT}/state"
ENROLLMENT_DIR="${DATA_ROOT}/enrollment"
POSTGRES_SECRET_NAME="${HEARTHGHOST_POSTGRES_SECRET_NAME:-}"
POSTGRES_SECRET_TARGET="hearthghost-postgres-dsn"
MEMORY_PRINCIPAL_BINDING="${HEARTHGHOST_MEMORY_PRINCIPAL_BINDING:-}"

require_repository_root() {
    test -f Dockerfile
    test -f docs/adr/0006-development-node-gateway-runtime.md
}

build_image() {
    podman build --pull=always --target development-core -t "${IMAGE}" .
}

initialize() {
    require_repository_root
    umask 077
    mkdir -p "${DATA_ROOT}" "${STATE_DIR}" "${ENROLLMENT_DIR}"
    chmod 700 "${DATA_ROOT}" "${STATE_DIR}" "${ENROLLMENT_DIR}"
    if [[ ! -d "${AUTHORITY_DIR}" ]]; then
        python -m apps.assistant.src.runtime.development_pki \
            initialize-authority \
            --authority-dir "${AUTHORITY_DIR}"
    fi
    if [[ ! -d "${TLS_DIR}" ]]; then
        python -m apps.assistant.src.runtime.development_pki \
            issue-server \
            --authority-dir "${AUTHORITY_DIR}" \
            --output-dir "${TLS_DIR}" \
            --server-ip "${HOST_IP}"
    fi
    podman run --rm \
        --userns=keep-id:uid=10001,gid=10001 \
        --network none \
        --read-only \
        --tmpfs /tmp:rw,noexec,nosuid,size=16m \
        --cap-drop=all \
        --security-opt=no-new-privileges \
        --mount "type=bind,src=${STATE_DIR},dst=/var/lib/hearthghost,rw,relabel=shared" \
        "${IMAGE}" \
        python -c 'from apps.assistant.src.adapters.development_state import DevelopmentStateFile; DevelopmentStateFile("/var/lib/hearthghost/state.json")'
}

create_network() {
    if ! podman network exists "${NETWORK}"; then
        podman network create \
            --internal \
            --subnet "${NETWORK_SUBNET}" \
            "${NETWORK}" >/dev/null
    fi
}

configure_postgres_secret() {
    POSTGRES_SECRET_ARGS=()
    POSTGRES_RUNTIME_ARGS=()
    if [[ -z "${POSTGRES_SECRET_NAME}" ]]; then
        return
    fi
    if [[ ! "${POSTGRES_SECRET_NAME}" =~ ^[A-Za-z0-9_.-]+$ ]]; then
        printf 'invalid HEARTHGHOST_POSTGRES_SECRET_NAME\n' >&2
        exit 2
    fi
    if ! podman secret exists "${POSTGRES_SECRET_NAME}"; then
        printf 'required Podman secret does not exist: %s\n' "${POSTGRES_SECRET_NAME}" >&2
        exit 2
    fi
    POSTGRES_SECRET_ARGS=(
        --secret "source=${POSTGRES_SECRET_NAME},type=mount,target=${POSTGRES_SECRET_TARGET},uid=10001,gid=10001,mode=0400"
    )
    POSTGRES_RUNTIME_ARGS=(
        --postgres-dsn-secret "/run/secrets/${POSTGRES_SECRET_TARGET}"
    )
}

configure_memory_principal() {
    MEMORY_PRINCIPAL_ARGS=()
    if [[ -z "${MEMORY_PRINCIPAL_BINDING}" ]]; then
        return
    fi
    if [[ ! "${MEMORY_PRINCIPAL_BINDING}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}=(user|household):[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]]; then
        printf 'invalid HEARTHGHOST_MEMORY_PRINCIPAL_BINDING\n' >&2
        exit 2
    fi
    MEMORY_PRINCIPAL_ARGS=(
        --memory-principal "${MEMORY_PRINCIPAL_BINDING}"
    )
}

deploy() {
    require_repository_root
    ip -brief address show | grep -Fq "${HOST_IP}/"
    configure_postgres_secret
    configure_memory_principal
    build_image
    initialize
    create_network
    if podman container exists "${CONTAINER}"; then
        podman rm --force "${CONTAINER}" >/dev/null
    fi
    podman run -d \
        --name "${CONTAINER}" \
        --restart=unless-stopped \
        --userns=keep-id:uid=10001,gid=10001 \
        --network "${NETWORK}" \
        --ip "${CONTAINER_IP}" \
        --publish "${HOST_IP}:${HOST_PORT}:${CONTAINER_PORT}" \
        --read-only \
        --tmpfs /tmp:rw,noexec,nosuid,size=16m \
        --cap-drop=all \
        --security-opt=no-new-privileges \
        --pids-limit=128 \
        --memory=256m \
        --cpus=1 \
        --mount "type=bind,src=${STATE_DIR},dst=/var/lib/hearthghost,rw,relabel=shared" \
        --mount "type=bind,src=${TLS_DIR},dst=/run/hearthghost-tls,ro,relabel=shared" \
        "${POSTGRES_SECRET_ARGS[@]}" \
        --health-cmd 'python -m apps.assistant.src.runtime.healthcheck' \
        --health-interval=10s \
        --health-timeout=3s \
        --health-retries=3 \
        "${IMAGE}" \
        python -m apps.assistant.src.runtime.development_server \
        --state /var/lib/hearthghost/state.json \
        --certificate /run/hearthghost-tls/server.crt \
        --private-key /run/hearthghost-tls/server.key \
        --client-ca /run/hearthghost-tls/client-ca.crt \
        "${POSTGRES_RUNTIME_ARGS[@]}" \
        "${MEMORY_PRINCIPAL_ARGS[@]}"
}

admin() {
    podman run --rm \
        --userns=keep-id:uid=10001,gid=10001 \
        --network none \
        --read-only \
        --tmpfs /tmp:rw,noexec,nosuid,size=16m \
        --cap-drop=all \
        --security-opt=no-new-privileges \
        --mount "type=bind,src=${STATE_DIR},dst=/var/lib/hearthghost,rw,relabel=shared" \
        --mount "type=bind,src=${ENROLLMENT_DIR},dst=/development-enrollment,ro,relabel=shared" \
        "${IMAGE}" \
        python -m apps.assistant.src.runtime.development_admin \
        --state /var/lib/hearthghost/state.json \
        "$@"
}

status() {
    podman inspect "${CONTAINER}" \
        --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}} {{json .NetworkSettings.Ports}}'
    podman exec "${CONTAINER}" python -m apps.assistant.src.runtime.healthcheck
}

stop_runtime() {
    if podman container exists "${CONTAINER}"; then
        podman stop "${CONTAINER}" >/dev/null
    fi
}

case "${1:-}" in
    build)
        build_image
        ;;
    initialize)
        build_image
        initialize
        ;;
    deploy)
        deploy
        ;;
    admin)
        shift
        admin "$@"
        ;;
    status)
        status
        ;;
    stop)
        stop_runtime
        ;;
    *)
        printf 'usage: %s {build|initialize|deploy|admin|status|stop}\n' "$0" >&2
        exit 2
        ;;
esac
