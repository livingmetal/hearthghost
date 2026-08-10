FROM python:3.13-slim-bookworm AS test

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

COPY --chown=hearthghost:hearthghost . .

USER hearthghost

CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]
