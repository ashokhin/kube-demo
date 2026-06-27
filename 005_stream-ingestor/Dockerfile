# stream-ingestor — Spark Structured Streaming: Kafka → HDFS Parquet + Hive
#
# Spark runs embedded via the pyspark pip package (bundles all JARs).
# Java 21 is installed to satisfy the JVM requirement at runtime.
# The Kafka connector jar (spark-sql-kafka) must be added separately.
#
# Init container KRB5 pattern:
#   An init container runs kinit before this container starts.
#   The TGT is shared via an emptyDir mounted at /tmp/krb5.
#   This container picks it up via KRB5CCNAME=/tmp/krb5/tgt.

# --- builder stage: install Python deps without JVM (for testing) ---
FROM python:3.12-slim AS builder

WORKDIR /build
COPY setup.py .
COPY src/ src/

# pyspark is large and not needed for the test suite (MOCK_MODE=true).
# sasl/pyhive/thrift are in the optional [hadoop] extra, not installed here.
# hadolint ignore=DL3013
RUN pip install --no-cache-dir --prefix=/install pytest ruff pydantic-settings prometheus-client
RUN pip install --no-cache-dir --prefix=/install --no-deps .

# --- runtime stage: Python 3.12 + Java + PySpark ---
FROM python:3.12-slim AS runtime

USER root

# Java 21 headless: required by PySpark (JVM must be present at runtime)
# Kerberos client libraries (needed for GSSAPI / HDFS auth)
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    krb5-user \
    libkrb5-3 \
    libsasl2-modules-gssapi-mit \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64

# Install PySpark (bundles Spark jars ~300 MB)
# hadolint ignore=DL3013
RUN pip install --no-cache-dir "pyspark>=3.5.0"

# Kafka connector for Spark Structured Streaming (must match pyspark version, Scala 2.12)
ENV SPARK_KAFKA_JAR=spark-sql-kafka-0-10_2.12-3.5.0.jar
RUN PYSPARK_DIR=$(python -c "import pyspark; import os; print(os.path.dirname(pyspark.__file__))") && \
    curl -fsSL \
    "https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.0/${SPARK_KAFKA_JAR}" \
    -o "${PYSPARK_DIR}/jars/${SPARK_KAFKA_JAR}"

# Copy Python packages from builder
COPY --from=builder /install /usr/local

COPY src/ /app/src/
COPY migrations/ /app/migrations/

WORKDIR /app

# Prometheus metrics port
EXPOSE 9090

# Non-root user
RUN useradd --system --create-home --uid 1001 appuser
USER appuser

ENTRYPOINT ["python", "-m", "src.main"]
