FROM python:3.13-slim-bookworm AS runtime-base

ARG HEARTHGHOST_UID=10001
ARG HEARTHGHOST_GID=10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER root
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-runtime.txt /tmp/requirements-runtime.txt
RUN pip install --no-cache-dir -r /tmp/requirements-runtime.txt \
    && rm /tmp/requirements-runtime.txt

RUN groupadd --gid "${HEARTHGHOST_GID}" hearthghost \
    && useradd --uid "${HEARTHGHOST_UID}" \
        --gid "${HEARTHGHOST_GID}" \
        --no-create-home \
        --shell /usr/sbin/nologin \
        hearthghost

WORKDIR /workspace
USER hearthghost

FROM runtime-base AS test

COPY --chown=hearthghost:hearthghost . .

CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]

FROM runtime-base AS core

COPY --chown=hearthghost:hearthghost apps ./apps
COPY --chown=hearthghost:hearthghost contracts ./contracts

CMD ["python", "-m", "apps.assistant.src.runtime.core"]

FROM runtime-base AS mock-node

COPY --chown=hearthghost:hearthghost apps ./apps
COPY --chown=hearthghost:hearthghost contracts ./contracts

CMD ["python", "-m", "apps.mock_node.src.client", "--check"]

FROM runtime-base AS client-node

COPY --chown=hearthghost:hearthghost apps ./apps
COPY --chown=hearthghost:hearthghost contracts ./contracts

CMD ["python", "-m", "apps.client_node.src.client", "--check"]

FROM core AS openai-smoke

CMD ["python", "-m", "apps.assistant.src.runtime.openai_smoke", "--adapter", "openai"]

FROM node:22-bookworm-slim AS windows-web-build

WORKDIR /workspace/apps/web-client
COPY apps/web-client/package.json apps/web-client/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY apps/web-client ./
RUN npm run assets:prepare \
    && npm run build

FROM mcr.microsoft.com/dotnet/sdk:10.0-bookworm-slim AS windows-native-build

WORKDIR /workspace
COPY .hearthghost-release /tmp/hearthghost-release
COPY apps/windows-client/HearthGhost.WindowsClient.csproj apps/windows-client/
RUN dotnet restore apps/windows-client/HearthGhost.WindowsClient.csproj \
        --runtime win-x64 \
        -p:EnableWindowsTargeting=true
COPY apps/windows-client apps/windows-client
RUN HEARTHGHOST_RELEASE_ID="$(cat /tmp/hearthghost-release)" \
    && test -n "${HEARTHGHOST_RELEASE_ID}" \
    && dotnet publish apps/windows-client/HearthGhost.WindowsClient.csproj \
        --configuration Release \
        --runtime win-x64 \
        --self-contained false \
        --no-restore \
        -p:EnableWindowsTargeting=true \
        -p:InformationalVersion="${HEARTHGHOST_RELEASE_ID}" \
        --output /windows-client \
    && printf '%s\n' "${HEARTHGHOST_RELEASE_ID}" > /windows-client/.hearthghost-release

FROM core AS development-core

COPY --from=windows-native-build --chown=hearthghost:hearthghost /windows-client /opt/hearthghost/windows-client
COPY --from=windows-web-build --chown=hearthghost:hearthghost /workspace/apps/web-client/dist /opt/hearthghost/windows-client/web

CMD ["python", "-m", "apps.assistant.src.runtime.development_server", "--state", "/var/lib/hearthghost/state.json", "--certificate", "/run/hearthghost-tls/server.crt", "--private-key", "/run/hearthghost-tls/server.key", "--client-ca", "/run/hearthghost-tls/client-ca.crt"]

FROM test AS walking-skeleton

CMD ["python", "-m", "unittest", "-v", "tests.integration.test_text_walking_skeleton_e2e"]

FROM node:22-bookworm-slim AS client-test

WORKDIR /workspace/apps/web-client

COPY --chown=node:node apps/web-client/package.json apps/web-client/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund

COPY --chown=node:node apps/web-client ./

RUN npm run check \
    && npm test \
    && npm run build

USER node

CMD ["node", "--test", "tests/client-node.test.mjs", "tests/character-presentation.test.mjs", "tests/conversation-controller.test.mjs", "tests/conversation-protocol.test.mjs"]
