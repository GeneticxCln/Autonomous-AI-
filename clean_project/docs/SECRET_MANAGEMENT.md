# Secret Management Guide

Secure environments must never rely on inline `.env` files or baked-in Docker
variables. The production deployment is expected to fetch secrets from a managed
store and inject them at runtime.

## Required secrets

| Secret | Purpose | Minimum requirements |
| --- | --- | --- |
| `JWT_SECRET_KEY` | Access/refresh token signing | Random, >= 32 chars |
| `DEFAULT_ADMIN_PASSWORD` | Bootstrap admin rotation | Random, >= 12 chars, rotated after each deploy |
| `DATABASE_URL` / `POSTGRES_PASSWORD` | Primary database credentials | Generated per environment |
| `REDIS_URL` | Redis auth / TLS config | Use ACL or managed Redis credentials |
| `GRAFANA_PASSWORD` | Monitoring UI login | Unique per environment |
| API keys (OpenAI, Anthropic, etc.) | External providers | Scoped to environment or tenant |

## Recommended pattern

1. Store each secret in AWS Secrets Manager, GCP Secret Manager, Hashicorp Vault,
   or Kubernetes `Secret` objects managed by an external controller.
2. CI/CD fetches secrets at deploy time and writes them to Kubernetes secrets via
   `kubectl apply -f -` or a GitOps operator.
3. Deployments reference those secrets via:
   ```yaml
   envFrom:
     - secretRef:
         name: agent-secrets
   ```
4. Production pods never mount `.env` files. Local development may still use
   `.env` for convenience, but the file must remain gitignored.

## Rotation checklist

- Rotate JWT and database credentials at least quarterly.
- Record rotations in the change log/runbook.
- Ensure old pods are recycled so that only the new secret copies remain in
  memory.
- Audit Git history and CI logs to confirm no secret values are printed.

## Validation

- `kubectl get secret agent-secrets -n agent-system -o yaml` should show only
  base64 blobs (never commit the decoded output).
- CI pipelines must fail if required secrets are missing; the application now
  raises at startup when weak defaults are detected.
