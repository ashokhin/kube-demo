# api-gateway

Single HTTP entry point for all external requests. Routes incoming traffic to internal
services and collects request metrics.

**Kubernetes workload: `Deployment`**

Deployment is used because:

- the service is stateless — any replica can handle any request
- horizontal scaling via HPA is needed
- replica startup order does not matter

See the workload comparison table: [README.md — When to use which workload](../README.md#when-to-use-which-kubernetes-workload)

## Stack

- Python 3.12
- FastAPI
- httpx (upstream proxying)
- prometheus-client

## Structure

- [src/main.py](src/main.py) — FastAPI app, routes, lifespan context manager
- [src/config.py](src/config.py) — pydantic-settings: env var mapping, ConfigMap vs Secret split
- [src/metrics.py](src/metrics.py) — Prometheus Counter and Histogram definitions
- [src/middleware.py](src/middleware.py) — per-request metrics and structured JSON logging
- [tests/test_main.py](tests/test_main.py) — endpoint tests with mocked httpx client
- [Dockerfile](Dockerfile) — multi-stage build, hatchling, non-root user
- [Jenkinsfile](Jenkinsfile) — CI pipeline: lint → test → build → push → promote to dev

## Configuration

All settings are injected via environment variables mounted from ConfigMap or Secret.

| Variable | Description | Default |
| --- | --- | --- |
| `ORDER_SERVICE_URL` | order-service base URL | `http://order-service:8080` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `PORT` | Application port | `8080` |

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/healthz` | Liveness probe |
| `GET` | `/readyz` | Readiness probe (checks upstream) |
| `GET` | `/metrics` | Prometheus metrics |
| `POST` | `/orders` | Create order → proxied to order-service |
| `GET` | `/orders/{id}` | Get order → proxied to order-service |

## Kubernetes resources

- Helm chart: [006_gitops/helm/api-gateway/](../006_gitops/helm/api-gateway/)
- Per-environment values: [values-dev.yaml](../006_gitops/helm/api-gateway/values-dev.yaml) / [values-staging.yaml](../006_gitops/helm/api-gateway/values-staging.yaml) / [values-prod.yaml](../006_gitops/helm/api-gateway/values-prod.yaml)
- Annotated manifests: [006_gitops/manifests/api-gateway/](../006_gitops/manifests/api-gateway/)
- ArgoCD Applications: [dev](../006_gitops/argocd/applications/dev/api-gateway.yaml) / [staging](../006_gitops/argocd/applications/staging/api-gateway.yaml) / [prod](../006_gitops/argocd/applications/api-gateway.yaml)
