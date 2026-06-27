# syntax=docker/dockerfile:1
#
# spark-calculator Dockerfile
#
# python-oracledb uses "thin mode" — no Oracle Instant Client required.
# If thick mode is needed (Advanced Queuing, DRCP, etc.), add Oracle Instant Client:
#
#   Option A: Download from public URL (requires accepting Oracle license at build time)
#     RUN curl -L https://download.oracle.com/otn_software/linux/instantclient/instantclient-basiclite-linux.x64-21.13.0.0.0dbru.zip -o /tmp/ic.zip && ...
#
#   Option B: Store the RPM/ZIP in Nexus and copy from there (recommended for enterprise):
#     COPY --from=nexus.company.internal/oracle/instantclient:21.13 /opt/oracle /opt/oracle
#
#   Option C: Use a pre-built base image that already includes Instant Client.
#
# For this demo, thin mode is sufficient — no extra steps needed.
#
# Spark runs embedded via pyspark pip package (bundles all JARs).
# Java 21 is installed to satisfy the JVM requirement.

# --- builder stage: install Python deps for testing ---
FROM python:3.12-slim AS builder

WORKDIR /app

# Install test-time deps only. pyspark is large (~300 MB); tests run in MOCK_MODE=true,
# so neither Spark nor oracledb are actually invoked during the test suite.
# hadolint ignore=DL3013
RUN pip install --no-cache-dir pytest ruff pydantic-settings oracledb

COPY setup.py .
COPY src/ ./src/
COPY tests/ ./tests/

# --- runtime stage: Python 3.12 + Java + PySpark ---
FROM python:3.12-slim AS runtime

WORKDIR /app

# Java 21 headless: required by PySpark (JVM must be present at runtime)
# krb5-user: kinit/klist for the init container Kerberos pattern
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
        openjdk-21-jre-headless \
        krb5-user \
        libkrb5-3 \
        && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64

# Install production dependencies.
# oracledb uses thin mode (pure Python wheel, no Instant Client).
# pyspark bundles Spark jars — no separate Spark installation needed.
# hadolint ignore=DL3013
RUN pip install --no-cache-dir \
    "pydantic-settings>=2.6.0" \
    "pyspark>=3.5.0" \
    "oracledb>=2.0.0"

COPY setup.py .
COPY src/ ./src/

# Non-root user
RUN useradd --system --create-home --uid 1000 appuser
USER appuser

# Job entrypoint — exits after completion (Kubernetes Job pattern)
CMD ["python", "-m", "src.main"]
