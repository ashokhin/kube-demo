# risk-engine

Long-running risk calculation service. Reads portfolio input data from HDFS,
computes VaR (Value-at-Risk) using a simplified model, and writes results to Hive.

**Kubernetes workload: `Deployment`**

Uses the **sidecar KRB5 pattern** for continuous Kerberos ticket renewal.

## Stack

- Python 3.12, FastAPI, poetry
- hdfs3 (HDFS client via libhdfs3, supports Kerberos GSSAPI)
- PyHive + sasl + thrift-sasl (Hive via Thrift/GSSAPI)
- Prometheus metrics

## Structure

```
002_risk-engine/
├── src/
│   ├── config.py           — pydantic-settings env var mapping
│   ├── main.py             — FastAPI app, POST /api/calculate endpoint
│   ├── hdfs_client.py      — HDFS read/write wrapper (mock_mode aware)
│   ├── hive_client.py      — Hive write wrapper via PyHive + GSSAPI
│   ├── risk_calculator.py  — Pure Python VaR calculation (no Hadoop deps)
│   └── metrics.py          — Prometheus counters and histograms
├── migrations/
│   ├── 000001_initial_schema.hql   — CREATE DATABASE, tables
│   └── 000002_add_stress_scenario.hql
├── migrate.sh              — Hive migration runner (beeline-based)
├── Dockerfile              — Multi-stage: poetry install → slim runtime
├── Dockerfile.migrate      — apache/hive image with beeline for migrations
└── Jenkinsfile
```

## Kerberos sidecar pattern

In Kubernetes, a `krb5-renewer` sidecar runs alongside the main container
and keeps the Kerberos ticket alive:

```
Pod
├── container: risk-engine        KRB5CCNAME=/tmp/krb5/tgt
│   └── reads TGT from emptyDir  ──────────────────────────┐
├── container: krb5-renewer                                 │
│   └── every 8h: kinit -R → writes TGT ───────────────────┘
└── volume: krb5-cache (emptyDir, shared)
```

The keytab (`risk-engine.keytab`) is mounted from a Kubernetes Secret.
The ticket cache (`/tmp/krb5/tgt`) is an `emptyDir` shared between both containers.

**Why sidecar and not init container?**
Init containers run once at pod startup. For a Deployment that lives for days/weeks,
the ticket would expire (typical lifetime: 10h, renewable up to 7 days).
The sidecar renews it continuously without restarting the main container.

See the Helm chart: [006_gitops/helm/risk-engine/](../006_gitops/helm/risk-engine/)

## Hive migrations

Migrations use numbered HiveQL scripts run by `migrate.sh` via `beeline`.
Applied versions are tracked in `risk.schema_migrations`.

```
migrations/
├── 000001_initial_schema.hql       — CREATE DATABASE risk; CREATE TABLE risk_results
└── 000002_add_stress_scenario.hql  — ALTER TABLE ADD COLUMNS scenario
```

Key differences from SQL (PostgreSQL/Alembic) migrations:

| | PostgreSQL (Alembic) | Hive (beeline scripts) |
|---|---|---|
| Rollback | `downgrade()` function | No — forward-only |
| Transactions | Yes — atomic | No — DDL has no transactions |
| Schema tracking | `alembic_version` table | `risk.schema_migrations` table |
| Idempotency | Alembic handles it | `IF NOT EXISTS` in every DDL |

The PreSync Job in ArgoCD runs `migrate.sh` before every deployment.
If all migrations are already applied, the job completes in seconds (no-op).

## Configuration

| Variable | Description | Source in K8s |
|----------|-------------|---------------|
| `MOCK_MODE` | Master switch — default for all three mock flags below | ConfigMap |
| `KAFKA_MOCK_MODE` | Simulate Kafka consumer (no real broker needed); falls back to `MOCK_MODE` | ConfigMap |
| `HDFS_MOCK_MODE` | Replace HDFS reads/writes with in-memory stubs; falls back to `MOCK_MODE` | ConfigMap |
| `HIVE_MOCK_MODE` | Replace Hive inserts with in-memory stubs; falls back to `MOCK_MODE` | ConfigMap |
| `HDFS_URL` | NameNode address | ConfigMap |
| `HDFS_INPUT_PATH` | Base HDFS path for portfolio inputs | ConfigMap |
| `HIVE_HOST` | HiveServer2 hostname | ConfigMap |
| `HIVE_DATABASE` | Hive database name | ConfigMap |
| `KRB5_KEYTAB_PATH` | Path to mounted keytab file | Secret (volume) |
| `KRB5_PRINCIPAL` | Kerberos principal | ConfigMap |
| `KRB5CCNAME` | Path to ticket cache (sidecar writes here) | ConfigMap |

### Mock flag precedence

```text
MOCK_MODE=false  KAFKA_MOCK_MODE=false  → real Kafka broker
                 HDFS_MOCK_MODE=true    → in-memory HDFS stubs (no hdfs3 needed)
                 HIVE_MOCK_MODE=true    → in-memory Hive stubs (no PyHive needed)
```

`docker-compose.yaml` sets only `MOCK_MODE=true` — all three subsystems are mocked.
`values-dev.yaml` sets `KAFKA_MOCK_MODE=false` + `HDFS/HIVE_MOCK_MODE=true` — real Kafka, mocked Hadoop.
