# syntax=docker/dockerfile:1
#
# oracle-reporter Dockerfile
#
# python-oracledb in THIN mode: no Oracle Instant Client needed.
# The driver is pure Python + a small C extension — installed via pip.
#
# If THICK mode is required (Advanced Queuing, sharded connections, etc.),
# add Oracle Instant Client. Recommended approaches:
#
#   Option A — store in Nexus, COPY from it (enterprise recommended):
#     COPY instantclient-basiclite-linux.x64-21.13.0.0.0.zip /tmp/
#     RUN unzip /tmp/instantclient-*.zip -d /opt/oracle && ...
#
#   Option B — use Oracle's public container image as a build stage:
#     COPY --from=container-registry.oracle.com/database/instantclient:21 \
#          /usr/lib/oracle/21/client64/lib /usr/lib/oracle/21/client64/lib
#
# Kerberos client tools are installed for the init container pattern:
#   kinit runs in the initContainer, krb5-user provides the kinit binary.

FROM python:3.12-slim AS builder

WORKDIR /app

# Install all dependencies including dev (for tests in builder stage).
# oracledb ships as a wheel (no C compiler needed for thin mode).
# hdfs3 requires libhdfs3 native libs — kept in requirements-hadoop.txt, not installed here.
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY src/ ./src/
COPY tests/ ./tests/
COPY migrations/ ./migrations/

# Runtime stage
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime dependencies:
#   libkrb5-3: Kerberos client for HDFS/Oracle GSSAPI
#   krb5-user: kinit, klist (used by the init container)
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
        libkrb5-3 \
        krb5-user \
        && rm -rf /var/lib/apt/lists/*

RUN useradd --system --create-home --uid 1000 appuser
USER appuser

COPY --from=builder --chown=appuser /usr/local/lib/python3.12/site-packages \
     /usr/local/lib/python3.12/site-packages
COPY --from=builder --chown=appuser /app/src ./src
COPY --from=builder --chown=appuser /app/migrations ./migrations

# CronJob: run to completion and exit
CMD ["python", "-m", "src.main"]
