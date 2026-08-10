FROM python:3.13-slim-bookworm AS runtime-base

ARG HEARTHGHOST_UID=10001
ARG HEARTHGHOST_GID=10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

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
