# spark-calculator

PySpark job that reads risk data from Hive, computes aggregated metrics, and writes results to Oracle.
Launched on demand by `risk-ui` via the Kubernetes API.

**Kubernetes workload: `Job`** (on demand, not scheduled)

Uses the **init container KRB5 pattern** — a one-time `kinit` before the main container starts.

## Stack

- Python 3.12, PySpark 3.5, setuptools
- PyHive (Hive input via Thrift/GSSAPI)
- python-oracledb thin mode (Oracle output, no Instant Client needed)

## Spark deployment modes

Controlled by a single `sparkMode` Helm value — all three modes use the same Docker image and Python code:

### `submit` — in-pod spark-submit (dev / small datasets)

```
Kubernetes Job pod
└── PySpark: spark-submit --master local[*]
    All Spark processing runs inside this single pod.
    No driver/executor split. Simple but resource-limited.
```

### `operator` — Spark Operator (production on Kubernetes)

```
Kubernetes Job pod (submit client)
└── SparkApplication CRD → Spark Operator
    ├── Driver pod  (created by operator)
    └── Executor pods × N (created by operator, scaled independently)
```

The Job pod submits the application and exits. The Operator manages the lifecycle.
See: [006_gitops/helm/spark-calculator/templates/spark-application.yaml](../006_gitops/helm/spark-calculator/templates/spark-application.yaml)

### `yarn` — external YARN (migration path from Hadoop cluster)

```
Kubernetes Job pod
└── spark-submit --master yarn → Hadoop YARN ResourceManager
    ├── YARN ApplicationMaster
    └── YARN Containers × N  (executors run on YARN NodeManagers)
```

Kubernetes only runs the submit client. Executors run on the existing YARN cluster.
Use this mode when migrating from a YARN-only cluster to Kubernetes incrementally.

## Kerberos init container pattern

```
Pod (spark-calculator Job)
├── initContainer: krb5-init
│     kinit -kt /keytab/spark-calculator.keytab spark-calc@EXAMPLE.COM
│     → writes TGT to /tmp/krb5/tgt
│     exits 0
└── container: spark-calculator
      KRB5CCNAME=/tmp/krb5/tgt  ← reads ticket written by init container
      PySpark connects to Hive via GSSAPI
```

The keytab is mounted from a Kubernetes Secret. The ticket cache is an `emptyDir`
shared between the init container and the main container via `volumes`.

**Why init container and not sidecar?**
This is a short-lived Job — it completes in minutes. The ticket lifetime (~10h)
far exceeds the job duration, so renewal is unnecessary.

## Configuration

| Variable | Description | Set by |
|----------|-------------|--------|
| `MODEL_VERSION` | Risk model version | risk-ui (K8s Job env) |
| `PORTFOLIO_ID` | Portfolio to process | risk-ui (K8s Job env) |
| `SCENARIO` | Calculation scenario | risk-ui (K8s Job env) |
| `SPARK_MODE` | Spark deployment mode | Helm values |
| `HIVE_HOST` | HiveServer2 hostname | ConfigMap |
| `ORACLE_DSN` | Oracle connection string | ConfigMap |
| `ORACLE_PASSWORD` | Oracle password | Secret |
| `KRB5CCNAME` | Ticket cache path | ConfigMap |
| `MOCK_MODE` | Replace Hadoop/Oracle with stubs | ConfigMap (dev only) |
