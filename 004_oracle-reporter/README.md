# oracle-reporter

Scheduled batch job that reads aggregated risk results from Oracle DB,
renders an HTML report with Jinja2, and uploads it to HDFS.

**Kubernetes workload: `CronJob`**

Uses the **init container KRB5 pattern** — one-time `kinit` before the main container starts.

## Stack

- Python 3.12, requirements.txt (no build system)
- python-oracledb thin mode (no Oracle Instant Client needed)
- hdfs3 (HDFS upload)
- Jinja2 (HTML report rendering)
- Alembic + SQLAlchemy (Oracle schema migrations)

## Structure

```
004_oracle-reporter/
├── src/
│   ├── config.py              — pydantic-settings env var mapping
│   ├── main.py                — CronJob entry point: Oracle → render → HDFS
│   ├── oracle_reader.py       — Fetch risk data from Oracle (mock-aware)
│   ├── report_renderer.py     — Jinja2 HTML renderer
│   └── templates/
│       └── report.html.j2     — HTML report template with risk-level color coding
├── migrations/
│   ├── alembic.ini            — Alembic config (DATABASE_URL from Secret)
│   ├── env.py                 — Alembic environment (oracle+oracledb:// dialect)
│   └── versions/
│       ├── 0001_initial_schema.py      — CREATE TABLE spark_risk_results
│       └── 0002_add_report_metadata.py — CREATE TABLE report_runs (audit log)
├── tests/
│   └── test_report_renderer.py
├── Dockerfile                 — Multi-stage, python-oracledb thin mode
└── Jenkinsfile
```

## Oracle migrations (Alembic)

Uses Alembic with the `oracle+oracledb` SQLAlchemy dialect.
`DATABASE_URL` is injected from a Kubernetes Secret at runtime.

```bash
# Apply migrations (run by the PreSync Job in Kubernetes)
DATABASE_URL=oracle+oracledb://user:pass@host:1521/ORCLPDB1 \
    alembic -c migrations/alembic.ini upgrade head

# Check current revision
alembic -c migrations/alembic.ini current

# Create a new migration
alembic -c migrations/alembic.ini revision --autogenerate -m "add column X"
```

Alembic differences from Hive migrations (002_risk-engine):

| | Hive (beeline scripts) | Oracle (Alembic) |
|---|---|---|
| Rollback | Not supported | `downgrade()` function |
| Transactions | No | Yes (DDL auto-commits in Oracle) |
| Schema tracking | Custom `schema_migrations` table | `alembic_version` table |
| Autogenerate | No | Yes — from SQLAlchemy models |

## python-oracledb thin mode

No Oracle Instant Client installation needed. The driver is installed via pip:

```
pip install oracledb
```

Connection string format:
```
oracle+oracledb://user:password@host:port/service_name
```

Thick mode (with Instant Client) is needed only for:
- Advanced Queuing (AQ)
- Sharded connections
- Oracle 11g (thin mode requires Oracle 12.1+)

See the Dockerfile for thick mode installation options.

## Configuration

| Variable | Description | Source in K8s |
|----------|-------------|---------------|
| `MOCK_MODE` | Replace Oracle/HDFS with stubs | ConfigMap |
| `ORACLE_DSN` | Oracle connection DSN | ConfigMap |
| `ORACLE_USER` | Oracle username | ConfigMap |
| `ORACLE_PASSWORD` | Oracle password | Secret |
| `HDFS_URL` | HDFS NameNode address | ConfigMap |
| `HDFS_OUTPUT_PATH` | HDFS base path for reports | ConfigMap |
| `KRB5CCNAME` | Ticket cache path (written by init container) | ConfigMap |
| `REPORT_LOOKBACK_DAYS` | Days of data to include in report | ConfigMap |
| `DATABASE_URL` | Full Oracle URL for Alembic | Secret |
