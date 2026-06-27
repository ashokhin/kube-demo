# Vault + External Secrets Operator

## Why

Keytabs and database passwords must not be stored in Git.
HashiCorp Vault is the authoritative secret store across all environments (dev, staging, prod) —
External Secrets Operator (ESO) syncs secrets into Kubernetes automatically,
so ArgoCD never needs to touch credentials directly.

## How it works

```text
Vault KV (secrets/)
  └─► ExternalSecret (ESO CRD)
        └─► Kubernetes Secret   ← mounted into pod as file / env var
```

ESO polls Vault on a configurable interval (default `1h`).
When a keytab is rotated in Vault, ESO refreshes the Kubernetes Secret,
and the pod picks it up on the next kinit cycle (sidecar) or Job restart (init container).

## Prerequisites

1. Vault deployed and unsealed (e.g. via the official Vault Helm chart).
2. External Secrets Operator installed:

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm upgrade --install external-secrets external-secrets/external-secrets \
  -n external-secrets --create-namespace
```

3. Kubernetes auth method enabled in Vault:

```bash
vault auth enable kubernetes
vault write auth/kubernetes/config \
  kubernetes_host="https://$KUBERNETES_PORT_443_TCP_ADDR:443"
```

## Manifests in this directory

| File | Purpose |
|------|---------|
| `cluster-secret-store.yaml` | ClusterSecretStore — Vault connection + K8s auth |
| `external-secrets.yaml` | ExternalSecret CRDs — one per service keytab + Oracle password |

## Vault secret layout

```text
secrets/
  hadoop-demo/
    risk-engine/
      keytab        ← base64-encoded risk-engine.keytab
    spark-calculator/
      keytab        ← base64-encoded spark-calculator.keytab
    oracle-reporter/
      keytab        ← base64-encoded oracle-reporter.keytab
      oracle-password
    stream-ingestor/
      keytab        ← base64-encoded stream-ingestor.keytab
```

Load a keytab into Vault:

```bash
vault kv put secrets/hadoop-demo/risk-engine \
  keytab="$(base64 -w0 risk-engine.keytab)"
```

## Vault policy

```hcl
path "secrets/data/hadoop-demo/*" {
  capabilities = ["read"]
}
```

Apply it and bind to the Kubernetes service account:

```bash
vault policy write hadoop-demo-reader hadoop-demo-policy.hcl

vault write auth/kubernetes/role/hadoop-demo-reader \
  bound_service_account_names="*" \
  bound_service_account_namespaces="hadoop-demo-dev,hadoop-demo-staging,hadoop-demo-prod" \
  policies="hadoop-demo-reader" \
  ttl=1h
```
