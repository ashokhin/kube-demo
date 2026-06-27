# db-migrator

Applies database migrations before application services start. Guarantees the schema
is up to date before any service pod begins serving traffic.

**Kubernetes workload: `Job`**

Job is used because:

- the task must run **exactly once** and exit successfully
- no long-lived process is needed
- on failure Kubernetes retries the pod (controlled by `backoffLimit`)
- application services must start **after** the Job completes (enforced via ArgoCD
  PreSync hook or `initContainers`)

See the workload comparison table: [README.md — When to use which workload](../README.md#when-to-use-which-kubernetes-workload)

## Stack

- Python 3.12
- Alembic
- SQLAlchemy + psycopg2 (sync driver — Alembic runs synchronously)

## Structure

- [src/env.py](src/env.py) — Alembic environment: reads DATABASE_URL from env, NullPool rationale
- [src/config.py](src/config.py) — pydantic-settings: DATABASE_URL, sync driver note
- [src/versions/0001_initial.py](src/versions/0001_initial.py) — initial schema migration
- [tests/test_config.py](tests/test_config.py) — config and migration file structure tests
- [Dockerfile](Dockerfile) — multi-stage build, poetry-core backend, non-root user
- [pyproject.toml](pyproject.toml) — poetry-core build backend (see comment for migration notes)

## Configuration

| Variable | Description | Source in K8s |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL connection string | Secret |

## Execution order in Kubernetes

The Job runs as an ArgoCD PreSync hook — before any other resources are applied.
See the hook annotations in the manifest: [006_gitops/manifests/db-migrator/job.yaml](../006_gitops/manifests/db-migrator/job.yaml)

```yaml
metadata:
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: BeforeHookCreation
```

Sequence:

1. ArgoCD sync triggered (git push or manual)
2. **PreSync phase** — db-migrator Job runs and must complete successfully
3. **Sync phase** — Deployments, Services, ConfigMaps applied
4. **PostSync phase** — optional smoke tests or notifications

For sync wave ordering across services see: [006_gitops/README.md — ArgoCD sync waves](../006_gitops/README.md#argocd-sync-waves)

## Kubernetes resources

- Helm chart: [006_gitops/helm/db-migrator/](../006_gitops/helm/db-migrator/)
- Per-environment values: [values-dev.yaml](../006_gitops/helm/db-migrator/values-dev.yaml) / [values-staging.yaml](../006_gitops/helm/db-migrator/values-staging.yaml) / [values-prod.yaml](../006_gitops/helm/db-migrator/values-prod.yaml)
- Annotated manifests: [006_gitops/manifests/db-migrator/](../006_gitops/manifests/db-migrator/)
- ArgoCD Applications: [dev](../006_gitops/argocd/applications/dev/db-migrator.yaml) / [staging](../006_gitops/argocd/applications/staging/db-migrator.yaml) / [prod](../006_gitops/argocd/applications/db-migrator.yaml)
