# ArgoCD Bootstrap Guide

This guide walks through installing ArgoCD into a fresh Kubernetes cluster and
bootstrapping the entire kube-demo application fleet using the **App of Apps** pattern.

---

## Why App of Apps instead of applying each manifest manually?

Without App of Apps you must apply every Application manifest by hand:

```bash
kubectl apply -f applications/dev/api-gateway.yaml
kubectl apply -f applications/dev/order-service.yaml
kubectl apply -f applications/dev/notification-service.yaml
# ... repeat for every service, every environment
```

Problems with the manual approach:

- Easy to forget a file or apply the wrong environment's manifests.
- When you add a new service, you must remember to `kubectl apply` its Application.
- The Application manifests themselves are not tracked by ArgoCD — only their targets are.
  ArgoCD does not know if an Application drifts from what is in git.

With App of Apps:

- You apply **one** root Application (`kube-demo-apps.yaml`) — once, ever.
- ArgoCD reads the `applications/dev/` directory and creates all child Applications.
- Adding a new service = add a YAML to `applications/dev/` and push. ArgoCD picks it up.
- All Application objects are themselves managed by ArgoCD, so any manual change is
  reverted (selfHeal) and deletions from git are reflected in the cluster (prune).

---

## Prerequisites

- `kubectl` configured to talk to the target cluster (`kubectl cluster-info` works).
- `helm` v3 installed (used for infrastructure dependencies).
- Git access to `https://github.com/ashokhin/gitops.git` from within the cluster
  (ArgoCD pulls from this URL).

---

## Step 1 — Install ArgoCD

```bash
kubectl create namespace argocd

kubectl apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

This creates the ArgoCD CRDs, RBAC, and all ArgoCD components in the `argocd` namespace.

---

## Step 2 — Wait for ArgoCD to be ready

```bash
kubectl wait --for=condition=available deployment/argocd-server \
  -n argocd --timeout=120s
```

Retrieve the auto-generated initial admin password:

```bash
kubectl get secret argocd-initial-admin-secret -n argocd \
  -o jsonpath="{.data.password}" | base64 -d
echo   # print a newline after the password
```

Save this password — you will need it in Step 8.

---

## Step 3 — Access the ArgoCD UI

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Open `https://localhost:8080` in a browser (accept the self-signed certificate warning).
Log in with username `admin` and the password from Step 2.

Leave this terminal open, or run the port-forward in the background:

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443 &
```

---

## Step 4 — Create the application namespaces

```bash
kubectl create namespace kube-demo-dev
kubectl create namespace kube-demo-staging
kubectl create namespace kube-demo-prod
```

---

## Step 5 — Apply namespace resource quotas and limits

```bash
kubectl apply -f 006_gitops/manifests/namespaces/
```

This sets per-namespace `ResourceQuota` and `LimitRange` objects that cap CPU/memory
usage and enforce default container limits.

---

## Step 6 — Apply the AppProject

The `AppProject` scopes which git repositories and destination namespaces ArgoCD may use.
Without it, child Applications cannot be created under the `kube-demo` project.

```bash
kubectl apply -f 006_gitops/argocd/projects/kube-demo.yaml
```

---

## Step 7 — Install the monitoring stack

The application Helm charts include `ServiceMonitor` resources (Prometheus Operator CRD).
If ArgoCD tries to sync these charts before the CRDs exist, `helm template` will fail.
Install the monitoring stack **before** bootstrapping the application fleet.

ArgoCD handles this automatically via sync waves (monitoring Applications have
`sync-wave: "-1"`), but only after the root Application is applied. On a fresh cluster
you must install the CRDs first:

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# kube-prometheus-stack installs Prometheus Operator + Prometheus + Grafana + Alertmanager
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --set grafana.adminPassword=CHANGEME \
  --wait

# Grafana Loki (log aggregation) — SingleBinary mode for dev
helm install loki grafana/loki \
  --namespace monitoring \
  --set loki.auth_enabled=false \
  --set deploymentMode=SingleBinary \
  --set singleBinary.replicas=1 \
  --wait

# Grafana Alloy (log collector) — replaces Promtail (EOL March 2, 2026)
helm install alloy grafana/alloy \
  --namespace monitoring \
  --wait
```

Verify that Prometheus Operator CRDs are installed:

```bash
kubectl get crd | grep monitoring.coreos.com
# Expected: servicemonitors, prometheusrules, podmonitors, ...
```

---

## Step 8 — Bootstrap with App of Apps

Apply the root Application. ArgoCD will discover and create all child Applications
in `006_gitops/argocd/applications/dev/` automatically.

```bash
# dev environment (apply first — safest environment to validate the fleet)
kubectl apply -f 006_gitops/argocd/applications/kube-demo-apps.yaml

# staging environment (after dev is verified healthy)
kubectl apply -f 006_gitops/argocd/applications/kube-demo-apps-staging.yaml

# prod environment (after staging is verified healthy)
kubectl apply -f 006_gitops/argocd/applications/kube-demo-apps-prod.yaml
```

ArgoCD will sync within 3 minutes (its default poll interval), or immediately if you
trigger a manual sync (see Step 9).

---

## Step 9 — Verify sync status

### Via the ArgoCD CLI

Install the CLI (if not already installed):

```bash
# Linux
curl -sSL -o /usr/local/bin/argocd \
  https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
chmod +x /usr/local/bin/argocd
```

Log in:

```bash
argocd login localhost:8080 \
  --username admin \
  --password <password-from-step-2> \
  --insecure
```

List all Applications and their sync/health status:

```bash
argocd app list
```

Trigger an immediate sync of the root Application (which cascades to children):

```bash
argocd app sync kube-demo-apps
```

Wait until the root Application and all children are synced and healthy:

```bash
argocd app wait kube-demo-apps --sync --health
```

### Via the ArgoCD UI

Open `https://localhost:8080`. The **Applications** view shows every Application as a tile
with its sync status (green = Synced, yellow = OutOfSync, red = Degraded).
Click any Application to see the full resource tree (Deployments, Pods, Services, etc.)
and the diff between the live cluster state and git.

---

## Step 10 — First deploy checklist

Before ArgoCD can deploy the application services successfully, the following
infrastructure must exist in each target namespace.

### 10.1 — Container registry access

Services pull images from the internal Nexus registry. Either:

- Configure the registry as unauthenticated (open) for the cluster's network, **or**
- Create an `imagePullSecret` in each namespace:

```bash
kubectl create secret docker-registry nexus-pull-secret \
  --docker-server=nexus.example.com \
  --docker-username=<user> \
  --docker-password=<password> \
  --namespace kube-demo-dev

# Repeat for kube-demo-staging and kube-demo-prod
```

Then reference the secret in each Helm values file (or add it to the chart's
`serviceAccount.imagePullSecrets`).

### 10.2 — PostgreSQL

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

helm install postgresql bitnami/postgresql \
  --namespace kube-demo-dev \
  --set auth.postgresPassword=CHANGEME \
  --set auth.database=kube_demo

# Repeat with appropriate values for staging and prod namespaces
```

### 10.3 — RabbitMQ

```bash
helm install rabbitmq bitnami/rabbitmq \
  --namespace kube-demo-dev \
  --set auth.username=kube-demo \
  --set auth.password=CHANGEME

# Repeat for staging and prod
```

### 10.4 — Application secrets

The Helm charts reference Kubernetes Secrets by name (they do not create them).
Replace every `CHANGEME` placeholder before the first sync:

```bash
# Example: create the order-service secret in dev
kubectl create secret generic kube-demo-order-service-secret \
  --namespace kube-demo-dev \
  --from-literal=DATABASE_URL="postgresql://kube-demo:CHANGEME@postgresql:5432/kube_demo" \
  --from-literal=RABBITMQ_URL="amqp://kube-demo:CHANGEME@rabbitmq:5672/"
```

Recommended for production: use [External Secrets Operator](https://external-secrets.io/)
to sync secrets from Vault, AWS Secrets Manager, or another secrets backend so that
plaintext credentials never appear in shell history or CI logs.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Root Application stuck `OutOfSync` | `kube-demo` AppProject not applied | Run Step 6 |
| Child Applications not appearing | Root Application not synced yet | `argocd app sync kube-demo-apps` |
| ServiceMonitor CRD not found | Monitoring stack not installed | Run Step 7 |
| Pods in `ImagePullBackOff` | Missing imagePullSecret or Nexus unreachable | See §10.1 |
| Pods in `CrashLoopBackOff` | Missing application Secret | See §10.4 |
| db-migrator fails | PostgreSQL not installed or wrong credentials | See §10.2 and §10.4 |

---

## Teardown

To remove everything ArgoCD manages (use with caution):

```bash
# Delete the root Applications — ArgoCD will cascade-delete child Applications
# and their resources (because of the resources-finalizer).
kubectl delete -f 006_gitops/argocd/applications/kube-demo-apps.yaml
kubectl delete -f 006_gitops/argocd/applications/kube-demo-apps-staging.yaml
kubectl delete -f 006_gitops/argocd/applications/kube-demo-apps-prod.yaml

# Remove ArgoCD itself
kubectl delete -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl delete namespace argocd
```
