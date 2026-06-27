# Kerberos secrets and config

## What lives here

- `krb5.conf` → ConfigMap (mounted at `/etc/krb5.conf` in all pods)
- Keytab files → Kubernetes Secrets (one per service principal)

## Keytab secrets

Keytab files are created by the Kerberos administrator and contain
the service principal's long-term key. They must **never** be committed to git.

Keytab secrets are managed by External Secrets Operator (ESO) across all environments.
ESO syncs them automatically from HashiCorp Vault — see [../vault/](../vault/).

Load keytabs into Vault once (per principal):

```bash
vault kv put secrets/hadoop-demo/risk-engine \
  keytab="$(base64 -w0 /path/to/risk-engine.keytab)"
vault kv put secrets/hadoop-demo/spark-calculator \
  keytab="$(base64 -w0 /path/to/spark-calculator.keytab)"
vault kv put secrets/hadoop-demo/oracle-reporter \
  keytab="$(base64 -w0 /path/to/oracle-reporter.keytab)" \
  oracle-password="<password>"
vault kv put secrets/hadoop-demo/stream-ingestor \
  keytab="$(base64 -w0 /path/to/stream-ingestor.keytab)"
```

ESO then creates the corresponding Kubernetes Secrets in each namespace automatically.

## How keytabs are mounted

Each Helm chart mounts the keytab as a read-only volume:

```yaml
volumes:
  - name: keytab
    secret:
      secretName: risk-engine-keytab
      defaultMode: 0400   # read-only for the owner (appuser uid 1000)
volumeMounts:
  - name: keytab
    mountPath: /keytab
    readOnly: true
```

The KRB5_KEYTAB_PATH env var points to `/keytab/<service>.keytab`.

## KRB5CCNAME — ticket cache

The ticket cache (TGT) is stored in an `emptyDir` volume shared between containers:

```yaml
volumes:
  - name: krb5-cache
    emptyDir: {}
```

- Init container (spark-calculator, oracle-reporter, stream-ingestor): writes TGT once, then exits
- Sidecar renewer (risk-engine): writes and renews TGT continuously

The main container reads the TGT via `KRB5CCNAME=/tmp/krb5/tgt`.
