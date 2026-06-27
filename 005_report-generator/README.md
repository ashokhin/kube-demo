# report-generator

Generates order summary reports on a schedule: queries PostgreSQL and writes the result
as JSON and CSV files. Demonstrates the scheduled batch processing pattern.

**Kubernetes workload: `CronJob`**

CronJob is used because:

- the task must run **repeatedly on a schedule** (cron syntax)
- each run is an independent Job that executes and exits
- no long-lived process is needed
- Kubernetes manages run history (`successfulJobsHistoryLimit`, `failedJobsHistoryLimit`)

See the workload comparison table: [README.md — When to use which workload](../README.md#when-to-use-which-kubernetes-workload)

## Stack

- Python 3.12
- SQLAlchemy + psycopg2
- Jinja2 (report templates)

## Structure

- [src/main.py](src/main.py) — entry point: runs report generation and exits with code 1 on failure
- [src/config.py](src/config.py) — env vars: DATABASE_URL (Secret), REPORT_OUTPUT_PATH, REPORT_PERIOD_DAYS
- [src/repository.py](src/repository.py) — sync SQLAlchemy engine, aggregate SQL query
- [src/renderer.py](src/renderer.py) — render_json / render_csv: idempotent file naming by date range
- [tests/test_renderer.py](tests/test_renderer.py) — pure function tests: file content, directory creation
- [Dockerfile](Dockerfile) — multi-stage build, pdm-backend, non-root user
- [pyproject.toml](pyproject.toml) — pdm-backend build backend (see comment for migration notes)

## Configuration

| Variable | Description | Source in K8s |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL connection string | Secret |
| `REPORT_OUTPUT_PATH` | Directory where reports are written | ConfigMap |
| `REPORT_PERIOD_DAYS` | Report time window in days | ConfigMap |
| `LOG_LEVEL` | Logging level | ConfigMap |

## Schedule

Configured via `spec.schedule` in cron syntax (UTC). Differs per environment:

| Environment | Schedule | Period |
| --- | --- | --- |
| dev | `*/30 * * * *` | every 30 minutes |
| staging | `0 6 * * *` | daily at 06:00 UTC |
| prod | `0 6 * * 1` | weekly on Monday |

See the annotated CronJob manifest: [006_gitops/manifests/report-generator/cronjob.yaml](../006_gitops/manifests/report-generator/cronjob.yaml)

## Important CronJob settings

| Field | Value | Why |
| --- | --- | --- |
| `concurrencyPolicy` | `Forbid` | Skip the new run if the previous one is still running |
| `startingDeadlineSeconds` | `300` | Do not catch up a missed run if it is more than 5 minutes late |
| `restartPolicy` | `Never` | On failure, create a new pod rather than restarting in place |

The application is **idempotent**: re-running it for the same period overwrites
the same output file with the same data. See [src/renderer.py](src/renderer.py) — date range in filename.

## Output storage

Reports are written to a `PersistentVolumeClaim` mounted at `REPORT_OUTPUT_PATH`.
The PVC is **managed outside the Helm chart** to prevent data loss on `helm uninstall`.

See: [006_gitops/manifests/report-generator/pvc.yaml](../006_gitops/manifests/report-generator/pvc.yaml)

### Accessing report files

The CronJob pod exits after each run. To inspect the generated files, use a
one-off debug pod that mounts the same PVC:

```bash
# Spin up a temporary pod with the PVC attached
kubectl run report-debug \
    --rm -it \
    --image=busybox \
    --restart=Never \
    --namespace=kube-demo-dev \
    --overrides='{
      "spec": {
        "volumes": [{"name":"reports","persistentVolumeClaim":{"claimName":"report-generator-pvc"}}],
        "containers": [{
          "name": "report-debug",
          "image": "busybox",
          "command": ["sh"],
          "volumeMounts": [{"name":"reports","mountPath":"/reports"}]
        }]
      }
    }'

# Inside the pod:
ls /reports
cat /reports/orders_2026-06-19_2026-06-26.json
exit    # pod is deleted automatically because of --rm
```

Alternatively, copy a file to your local machine with `kubectl cp`:

```bash
# First, find the most recent completed job pod
kubectl get pods -n kube-demo-dev -l app.kubernetes.io/name=report-generator

# Copy the file (replace <pod-name> with the actual pod name)
kubectl cp kube-demo-dev/<pod-name>:/reports/orders_2026-06-19_2026-06-26.json ./report.json
```

> **Note**: `kubectl cp` only works while the pod is still running. For completed
> (exited) pods use the debug pod approach above, which accesses the PVC directly.

## Kubernetes resources

- Helm chart: [006_gitops/helm/report-generator/](../006_gitops/helm/report-generator/)
- Per-environment values: [values-dev.yaml](../006_gitops/helm/report-generator/values-dev.yaml) / [values-staging.yaml](../006_gitops/helm/report-generator/values-staging.yaml) / [values-prod.yaml](../006_gitops/helm/report-generator/values-prod.yaml)
- Annotated manifests: [006_gitops/manifests/report-generator/](../006_gitops/manifests/report-generator/)
- ArgoCD Applications: [dev](../006_gitops/argocd/applications/dev/report-generator.yaml) / [staging](../006_gitops/argocd/applications/staging/report-generator.yaml) / [prod](../006_gitops/argocd/applications/report-generator.yaml)
