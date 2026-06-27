# syntax=docker/dockerfile:1

# Stage 1 — install dependencies with poetry
FROM python:3.12-slim AS builder

WORKDIR /app

# librdkafka-dev is required to build confluent-kafka (C extension)
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
        librdkafka-dev \
        gcc \
        && rm -rf /var/lib/apt/lists/*

# Install poetry. Pin the version for reproducible builds.
RUN pip install --no-cache-dir poetry==1.8.3

# Copy only the dependency manifest first — Docker caches this layer
# unless pyproject.toml or poetry.lock changes.
COPY pyproject.toml poetry.lock* ./

# Install production dependencies only (no dev group).
# --no-root: do not install the package itself yet (we'll COPY src later).
RUN poetry config virtualenvs.in-project true && \
    poetry install --only main --no-root --no-interaction

COPY src/ ./src/

# Stage 2 — minimal runtime image
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime system dependencies:
#   librdkafka1: confluent-kafka runtime (C extension)
#   libsasl2-modules-gssapi-mit: GSSAPI/Kerberos for PyHive authentication
#   libkrb5-3: Kerberos client libraries for GSSAPI
#   krb5-user: kinit, klist, kdestroy (used by the sidecar renewer)
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
        librdkafka1 \
        libsasl2-modules-gssapi-mit \
        libkrb5-3 \
        krb5-user \
        && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd --system --create-home --uid 1000 appuser
USER appuser

# Copy installed virtualenv and source from builder
COPY --from=builder --chown=appuser /app/.venv .venv
COPY --from=builder --chown=appuser /app/src ./src

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8081

CMD ["python", "-m", "src.main"]
