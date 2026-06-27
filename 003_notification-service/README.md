# notification-service

Notification dispatcher. Consumes order events from RabbitMQ and processes them
(logs, simulates email/SMS sending). Demonstrates the long-running consumer pattern
with graceful shutdown.

**Kubernetes workload: `Deployment`**

Deployment is used because:

- the service is stateless — no local state, no persistent storage
- it runs as a long-lived process (not a one-shot task)
- graceful shutdown is critical: the consumer must finish processing the current
  message before the pod exits

See the workload comparison table: [README.md — When to use which workload](../README.md#when-to-use-which-kubernetes-workload)

## Stack

- Python 3.12
- FastAPI (healthz/metrics only; main logic is the consumer loop)
- aio-pika (RabbitMQ)
- prometheus-client

## Structure

- [src/main.py](src/main.py) — entry point: starts consumer + HTTP server concurrently, registers SIGTERM handler
- [src/config.py](src/config.py) — env var mapping
- [src/consumer.py](src/consumer.py) — RabbitMQ consumer: connect_robust, prefetch_count=1, graceful shutdown via asyncio.Event
- [src/handlers.py](src/handlers.py) — YAML-based dispatch logic: loads routing rules from `handlers_config.yaml` at startup
- [src/handlers_config.yaml](src/handlers_config.yaml) — notification routing rules (event type → list of channels)
- [src/metrics.py](src/metrics.py) — Prometheus metrics: received/processed/failed counters, processing Histogram
- [tests/test_handlers.py](tests/test_handlers.py) — dispatch tests using a temporary config file (no RabbitMQ, no real YAML)
- [Dockerfile](Dockerfile) — multi-stage build, flit-core backend, non-root user
- [pyproject.toml](pyproject.toml) — flit-core build backend (see comment for migration notes)

## Configuration

| Variable | Description | Source in K8s |
| --- | --- | --- |
| `RABBITMQ_URL` | RabbitMQ connection string | Secret |
| `QUEUE_NAME` | Queue to consume from | ConfigMap |
| `LOG_LEVEL` | Logging level | ConfigMap |
| `PORT` | HTTP port (healthz/metrics) | ConfigMap |
| `HANDLERS_CONFIG_PATH` | Path to the YAML routing rules file | ConfigMap (env var) |

## Notification routing — ConfigMap as a file

Routing rules (`handlers_config.yaml`) define which channels to notify for each event type:

```yaml
handlers:
  order.created:
    - type: email
      template: order_confirmation
      retry: 3
    - type: push
      template: order_created_push
      retry: 1
  order.shipped:
    - type: sms
      template: order_shipped_sms
      retry: 2
default:
  - type: log
    level: warning
```

In Kubernetes the file is mounted from a ConfigMap:

```text
ConfigMap (handlers.yaml key)
       │
       ▼ volumeMount subPath
  /app/config/handlers.yaml   ← HANDLERS_CONFIG_PATH points here
       │
       ▼ yaml.safe_load() at startup
  handlers.py _routing dict
```

**Why a file and not env vars?**

| Env var (flat `KEY=VALUE`) | YAML file (structured) |
| --- | --- |
| `ORDER_CREATED_CHANNEL=email` | Full hierarchy: event → channels → options |
| Hard to express lists | Supports lists, nesting, comments |
| Must rebuild config for each new field | Add a new channel type without changing code |

Updating the routing rules requires only `helm upgrade` — no Docker image rebuild.
The checksum annotation in the Deployment triggers an automatic pod rollout when the
ConfigMap changes.

See the Helm chart: [006_gitops/helm/notification-service/templates/configmap.yaml](../006_gitops/helm/notification-service/templates/configmap.yaml)

## Graceful shutdown

When Kubernetes sends `SIGTERM` before killing the pod, the service:

1. Stops accepting new messages from the queue
2. Waits for the current message to finish processing
3. Closes the RabbitMQ connection
4. Exits cleanly

`terminationGracePeriodSeconds` in the Deployment (default: 60s) must be long enough
for step 2 to complete. If `SIGKILL` arrives mid-processing, the message is nacked
and returned to the queue.

Implementation: [src/consumer.py](src/consumer.py) — `_should_stop` asyncio.Event flag,
[src/main.py](src/main.py) — `loop.add_signal_handler(signal.SIGTERM, _stop)`.

See also: [README.md — Graceful shutdown](../README.md#graceful-shutdown)

## Kubernetes resources

- Helm chart: [006_gitops/helm/notification-service/](../006_gitops/helm/notification-service/)
- Per-environment values: [values-dev.yaml](../006_gitops/helm/notification-service/values-dev.yaml) / [values-staging.yaml](../006_gitops/helm/notification-service/values-staging.yaml) / [values-prod.yaml](../006_gitops/helm/notification-service/values-prod.yaml)
- Annotated manifests: [006_gitops/manifests/notification-service/](../006_gitops/manifests/notification-service/)
- ArgoCD Applications: [dev](../006_gitops/argocd/applications/dev/notification-service.yaml) / [staging](../006_gitops/argocd/applications/staging/notification-service.yaml) / [prod](../006_gitops/argocd/applications/notification-service.yaml)
