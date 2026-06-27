# Raw Kubernetes Manifests

This directory contains plain YAML manifests — the final form that Kubernetes actually receives.
They are **equivalent** to what Helm produces from the charts in `../helm/`, but written by hand
and heavily annotated to explain every field.

> **In a real project** you would never maintain both. You either use Helm (charts generate
> manifests at deploy time) or raw manifests (you write and maintain YAML directly). This
> directory exists purely for educational purposes: to show what Helm templates expand into
> and to explain each Kubernetes field in isolation.

---

## How Helm generates manifests

```
helm/api-gateway/
├── Chart.yaml       ← metadata: name, version, appVersion
├── values.yaml      ← your inputs (image tag, replicas, config, …)
└── templates/
    ├── _helpers.tpl ← Go template functions → reusable name/label snippets
    ├── deployment.yaml  ← Go template → rendered YAML
    └── …
```

The rendering command:

```bash
# Render locally without deploying (dry run):
helm template kube-demo ./helm/api-gateway \
  -f ./helm/api-gateway/values.yaml \
  --namespace kube-demo

# Render and apply:
helm upgrade --install kube-demo ./helm/api-gateway \
  -f ./helm/api-gateway/values.yaml \
  --namespace kube-demo --create-namespace
```

Charts: [api-gateway](../helm/api-gateway/) · [order-service](../helm/order-service/) · [notification-service](../helm/notification-service/) · [db-migrator](../helm/db-migrator/) · [report-generator](../helm/report-generator/)

`helm template` substitutes every `{{ .Values.* }}` and `{{ include "…" }}` call with
concrete values and writes the result to stdout.  What you see in this directory is that
output, manually formatted and annotated.

---

## From values.yaml to manifest: field mapping

Below is the mapping for `api-gateway`. The same logic applies to every other service.

```
values.yaml field                   → manifest location
─────────────────────────────────────────────────────────────────
image.repository + image.tag        → spec.template.spec.containers[0].image
image.pullPolicy                    → spec.template.spec.containers[0].imagePullPolicy
replicaCount                        → spec.replicas  (omitted when HPA is enabled)
service.port                        → Service.spec.ports[0].port
service.targetPort                  → Service.spec.ports[0].targetPort
config.*                            → ConfigMap.data  → envFrom.configMapRef
secrets.*                           → Secret.stringData → envFrom.secretRef
resources.requests/limits           → containers[0].resources
livenessProbe.*                     → containers[0].livenessProbe
readinessProbe.*                    → containers[0].readinessProbe
autoscaling.*                       → HorizontalPodAutoscaler.spec
ingress.*                           → Ingress.spec
serviceMonitor.*                    → ServiceMonitor.spec
```

### Where labels come from

`_helpers.tpl` defines two label sets:

| Template | Fields | Used in |
|---|---|---|
| `api-gateway.labels` | `helm.sh/chart`, `app.kubernetes.io/name`, `instance`, `version`, `managed-by` | `metadata.labels` of every resource |
| `api-gateway.selectorLabels` | `app.kubernetes.io/name`, `app.kubernetes.io/instance` | `spec.selector.matchLabels` in Deployment, `selector` in Service |

`selectorLabels` is a **subset** of `labels` — it must never change after first deploy because
Kubernetes uses it as an immutable key to link Deployment → ReplicaSet → Pod.

### The checksum annotation trick

```yaml
annotations:
  checksum/config: <sha256 of configmap.yaml template output>
  checksum/secret: <sha256 of secret.yaml template output>
```

Kubernetes does not restart pods when a ConfigMap changes. This annotation changes whenever
the ConfigMap or Secret content changes, which forces a new pod template hash → rolling
restart. Without it, pods keep running with stale environment variables.

---

## Release name convention

In these manifests the Helm release name is `kube-demo`, so all resource names follow
the pattern `kube-demo-<chart-name>` (from `_helpers.tpl` → `fullname`):

| Chart | Resource name | Manifests |
| --- | --- | --- |
| api-gateway | `kube-demo-api-gateway` | [manifests/api-gateway/](api-gateway/) |
| order-service | `kube-demo-order-service` | [manifests/order-service/](order-service/) |
| notification-service | `kube-demo-notification-service` | [manifests/notification-service/](notification-service/) |
| db-migrator | `kube-demo-db-migrator` | [manifests/db-migrator/](db-migrator/) |
| report-generator | `kube-demo-report-generator` | [manifests/report-generator/](report-generator/) |

---

## Applying manifests directly (without Helm)

```bash
# Create namespace
kubectl create namespace kube-demo

# Apply one service
kubectl apply -f manifests/api-gateway/ -n kube-demo

# Apply everything
kubectl apply -f manifests/ -n kube-demo --recursive
```
