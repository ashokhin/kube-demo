#!/bin/bash
# Hive migration runner — applies pending HiveQL scripts in order.
#
# Equivalent to golang-migrate but for Hive:
#   - Scripts are numbered (000001, 000002, ...)
#   - Applied versions are tracked in risk.schema_migrations
#   - Each script is idempotent (CREATE IF NOT EXISTS)
#   - NO rollback support — Hive DDL has no transactions
#
# Called by the Kubernetes PreSync Job (see 006_gitops/helm/risk-engine/templates/hive-migrate-job.yaml)
# KRB5CCNAME must be set before this script runs (done by the init container).

set -euo pipefail

HIVE_URL="${HIVE_URL:?HIVE_URL is required, e.g. jdbc:hive2://hive-server:10000/}"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-/migrations}"

echo "==> Hive migration runner"
echo "    HIVE_URL: ${HIVE_URL}"
echo "    KRB5CCNAME: ${KRB5CCNAME:-not set}"

# Ensure the schema_migrations table exists (first-run bootstrap).
# If it doesn't exist yet, this creates it. If it does, this is a no-op.
beeline -u "${HIVE_URL}" --silent=true -e "
    CREATE DATABASE IF NOT EXISTS risk;
    CREATE TABLE IF NOT EXISTS risk.schema_migrations (
        version STRING, applied_at TIMESTAMP, description STRING
    ) STORED AS PARQUET;
" 2>/dev/null || {
    echo "ERROR: Cannot connect to Hive at ${HIVE_URL}"
    echo "       Check HIVE_URL and KRB5CCNAME (ticket must be valid)"
    exit 1
}

# Get already-applied versions as a newline-separated list
APPLIED=$(beeline -u "${HIVE_URL}" --silent=true --outputformat=tsv2 \
    -e "SELECT version FROM risk.schema_migrations;" 2>/dev/null \
    | tail -n +2 || echo "")

echo "==> Applied versions: $(echo "${APPLIED}" | tr '\n' ' ')"

# Apply pending scripts in sorted order
APPLIED_COUNT=0
SKIPPED_COUNT=0

while IFS= read -r script; do
    version=$(basename "${script}" | cut -d_ -f1)

    if echo "${APPLIED}" | grep -q "^${version}$"; then
        echo "    SKIP ${script} (already applied)"
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        continue
    fi

    echo "==> APPLY ${script}"
    beeline -u "${HIVE_URL}" --silent=true -f "${script}"
    APPLIED_COUNT=$((APPLIED_COUNT + 1))
    echo "    OK"
done < <(find "${MIGRATIONS_DIR}" -name "*.hql" | sort)

echo "==> Done: ${APPLIED_COUNT} applied, ${SKIPPED_COUNT} skipped"
