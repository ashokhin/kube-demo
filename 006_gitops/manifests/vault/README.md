# External Secrets Operator + HashiCorp Vault

This directory contains the manifests that connect External Secrets Operator (ESO)
to HashiCorp Vault, enabling automatic Secret management in the cluster.

---

## What is External Secrets Operator

External Secrets Operator (ESO) is a Kubernetes operator that reads secrets from
external secret stores (HashiCorp Vault, AWS SSM, GCP Secret Manager, Azure Key Vault, etc.)
and automatically creates Kubernetes `Secret` objects from them.

**Why ESO instead of manually creating Secrets:**

| Manual approach | ESO approach |
| --- | --- |
| Engineer creates Secret by hand or via CI/CD script | ESO creates and updates Secrets automatically |
| Secret value in CI/CD variables or base64 in YAML | Secret value lives only in Vault — never in git or CI/CD |
| Rotation requires re-running the pipeline | Rotation requires only updating the value in Vault |
| No audit trail for secret access | Vault audit log shows every read |
| Secrets can drift between environments | ESO enforces the desired state on every reconcile |

**Data flow:**

```mermaid
graph TD
    Vault["HashiCorp Vault\n(stores passwords, API keys)"]
    Vault -->|"ESO polls every refreshInterval\n(default: 1h)"| ESO["External Secrets Operator\n(namespace: external-secrets)"]
    ESO -->|"creates / updates"| Secret["Kubernetes Secret\n(standard Secret in app namespace)"]
    Secret -->|"envFrom: secretRef"| Pod["Application pod\n(reads DATABASE_URL, RABBITMQ_URL etc. as env vars)"]
```

---

## Prerequisites

### 1. Install External Secrets Operator

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm repo update

helm install external-secrets external-secrets/external-secrets \
    -n external-secrets --create-namespace
```

Verify the operator is running:

```bash
kubectl get pods -n external-secrets
```

### 2. Configure Vault Kubernetes authentication

ESO authenticates to Vault using the Kubernetes auth method. Vault verifies ESO's
ServiceAccount token against the Kubernetes API server.

```bash
# Enable Kubernetes auth method in Vault
vault auth enable kubernetes

# Configure Vault to verify tokens against this cluster's API server
vault write auth/kubernetes/config \
    kubernetes_host="https://$KUBERNETES_PORT_443_TCP_ADDR:443"
```

### 3. Create Vault policy

The policy grants read access to all secrets under `secret/kube-demo/`:

```bash
vault policy write kube-demo - <<EOF
path "secret/data/kube-demo/*" {
  capabilities = ["read"]
}
EOF
```

Note: KV v2 stores secrets under `secret/data/<path>` in the API, even though
you write them as `secret/<path>` with the `vault kv put` CLI command.
The `secret/data/kube-demo/*` path in the policy covers all services and environments.

### 4. Create Vault role binding ESO ServiceAccount

```bash
vault write auth/kubernetes/role/kube-demo \
    bound_service_account_names=external-secrets \
    bound_service_account_namespaces=external-secrets \
    policies=kube-demo \
    ttl=1h
```

This role allows only the `external-secrets` ServiceAccount in the `external-secrets`
namespace to authenticate. Any other ServiceAccount is denied.

---

## Populating secrets in Vault (KV v2)

Store each service's secrets under the path `secret/kube-demo/<env>/<service>`.

```bash
# order-service — dev
vault kv put secret/kube-demo/dev/order-service \
    DATABASE_URL="postgresql+asyncpg://orders_user:REAL_PASSWORD@postgresql:5432/orders" \
    MIGRATE_DATABASE_URL="postgresql://orders_user:REAL_PASSWORD@postgresql:5432/orders" \
    RABBITMQ_URL="amqp://orders_user:REAL_PASSWORD@rabbitmq:5672/"

# notification-service — dev
vault kv put secret/kube-demo/dev/notification-service \
    RABBITMQ_URL="amqp://notifications_user:REAL_PASSWORD@rabbitmq:5672/"

# db-migrator — dev
vault kv put secret/kube-demo/dev/db-migrator \
    DATABASE_URL="postgresql://orders_user:REAL_PASSWORD@postgresql:5432/orders"

# report-generator — dev
vault kv put secret/kube-demo/dev/report-generator \
    DATABASE_URL="postgresql://orders_user:REAL_PASSWORD@postgresql:5432/orders"
```

Repeat for `staging` and `prod` environments, substituting the appropriate passwords.

Verify the secrets are stored correctly:

```bash
vault kv get secret/kube-demo/dev/order-service
```

---

## Applying the manifests

Apply the ClusterSecretStore first (cluster-scoped, applied once):

```bash
kubectl apply -f 006_gitops/manifests/vault/clusterSecretStore.yaml
```

Apply ExternalSecret manifests for each service:

```bash
kubectl apply -f 006_gitops/manifests/order-service/externalsecret.yaml
kubectl apply -f 006_gitops/manifests/notification-service/externalsecret.yaml
kubectl apply -f 006_gitops/manifests/db-migrator/externalsecret.yaml
kubectl apply -f 006_gitops/manifests/report-generator/externalsecret.yaml
```

Verify ESO synced the secrets successfully:

```bash
# Check ExternalSecret status — should show "SecretSynced" condition
kubectl get externalsecret -n kube-demo-dev

# Inspect a specific ExternalSecret for error details
kubectl describe externalsecret order-service -n kube-demo-dev

# Verify the resulting Kubernetes Secret was created
kubectl get secret order-service -n kube-demo-dev

# Check the Secret contains the expected keys (values are base64-encoded)
kubectl get secret order-service -n kube-demo-dev -o jsonpath='{.data}' | jq 'keys'
```

---

## Secret rotation

When a password changes, update it in Vault:

```bash
vault kv put secret/kube-demo/dev/order-service \
    DATABASE_URL="postgresql+asyncpg://orders_user:NEW_PASSWORD@postgresql:5432/orders" \
    MIGRATE_DATABASE_URL="postgresql://orders_user:NEW_PASSWORD@postgresql:5432/orders" \
    RABBITMQ_URL="amqp://orders_user:NEW_PASSWORD@rabbitmq:5672/"
```

ESO automatically detects the change on the next `refreshInterval` cycle (default: 1h)
and updates the Kubernetes Secret. No manual intervention is required.

**Immediate refresh** (without waiting for the next cycle):

```bash
kubectl annotate externalsecret order-service \
    force-sync=$(date +%s) \
    --overwrite \
    -n kube-demo-dev
```

**Pods do not automatically reload** when the Secret is updated — the new env var values
are only visible after a pod restart. Options:

- Restart the deployment manually: `kubectl rollout restart deployment/order-service -n kube-demo-dev`
- Install [Reloader by Stakater](https://github.com/stakater/Reloader) — it watches Secrets
  and automatically restarts Deployments when referenced Secrets change.

---

## Enabling ESO in Helm

By default, Helm charts in this project create the Secret from `values.yaml` (CHANGEME placeholders).
To switch a deployment to ESO-managed secrets:

1. Apply the ExternalSecret manifest for the service (see above).
2. Deploy the Helm chart with `externalSecrets.enabled=true`:

```bash
helm upgrade order-service ./helm/order-service \
    -f helm/order-service/values.yaml \
    -f helm/order-service/values-dev.yaml \
    --set externalSecrets.enabled=true \
    --namespace kube-demo-dev
```

When `externalSecrets.enabled=true`:
- The Helm `Secret` template is skipped (`{{- if and .Values.secrets (not .Values.externalSecrets.enabled) }}`).
- ESO is the sole owner of the Secret (`creationPolicy: Owner`).
- Deleting the ExternalSecret also deletes the Kubernetes Secret.

To revert to Helm-managed secrets (e.g. if ESO is removed from the cluster):

```bash
helm upgrade order-service ./helm/order-service \
    -f helm/order-service/values.yaml \
    -f helm/order-service/values-dev.yaml \
    --set externalSecrets.enabled=false \
    --namespace kube-demo-dev
```

The chart will recreate the Secret from the placeholder values in `values.yaml`.
Replace CHANGEME values with real credentials before applying.

---

## Vault KV v2 path structure reference

```
secret/                          ← KV v2 mount (configured in clusterSecretStore.yaml)
└── kube-demo/                   ← project namespace
    ├── dev/
    │   ├── order-service        ← DATABASE_URL, MIGRATE_DATABASE_URL, RABBITMQ_URL
    │   ├── notification-service ← RABBITMQ_URL
    │   ├── db-migrator          ← DATABASE_URL
    │   └── report-generator     ← DATABASE_URL
    ├── staging/
    │   └── ...                  ← same structure, different passwords
    └── prod/
        └── ...                  ← same structure, different passwords
```
