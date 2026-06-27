# Namespace Resource Constraints

This directory contains namespace-level resource constraints applied once per namespace
by a cluster admin. These are **not** part of the Helm charts — they are cluster-admin
resources that define the resource budget for each environment namespace.

## ResourceQuota

`ResourceQuota` caps the total resources the namespace can consume across all pods.
This prevents a misconfigured or runaway service from starving other namespaces on
the same node.

| Environment | requests.cpu | limits.cpu | requests.memory | limits.memory | pods |
|-------------|-------------|------------|-----------------|---------------|------|
| dev         | 4           | 8          | 4Gi             | 8Gi           | 20   |
| staging     | 8           | 16         | 8Gi             | 16Gi          | 40   |
| prod        | 16          | 32         | 16Gi            | 32Gi          | 100  |

## LimitRange

`LimitRange` sets default resource requests/limits for any container that does not
specify them explicitly. It also enforces minimum and maximum bounds per container,
preventing pods with no limits from consuming unbounded resources.

| Environment | default cpu/mem   | defaultRequest cpu/mem | max cpu/mem |
|-------------|-------------------|------------------------|-------------|
| dev         | 200m / 256Mi      | 50m / 64Mi             | 2 / 2Gi     |
| staging     | 200m / 256Mi      | 50m / 64Mi             | 2 / 2Gi     |
| prod        | 200m / 256Mi      | 50m / 64Mi             | 4 / 4Gi     |

## How to apply

Apply each file with `kubectl apply`. The namespace must exist beforehand.

```bash
# dev
kubectl apply -f 006_gitops/manifests/namespaces/resourcequota-dev.yaml
kubectl apply -f 006_gitops/manifests/namespaces/limitrange-dev.yaml

# staging
kubectl apply -f 006_gitops/manifests/namespaces/resourcequota-staging.yaml
kubectl apply -f 006_gitops/manifests/namespaces/limitrange-staging.yaml

# prod
kubectl apply -f 006_gitops/manifests/namespaces/resourcequota-prod.yaml
kubectl apply -f 006_gitops/manifests/namespaces/limitrange-prod.yaml
```

Or apply the entire directory at once:

```bash
kubectl apply -f 006_gitops/manifests/namespaces/
```

> Note: `kubectl apply -f <directory>` applies all `.yaml` files in the directory.
> Ensure the target namespaces (`kube-demo-dev`, `kube-demo-staging`, `kube-demo-prod`)
> exist before running the command.
