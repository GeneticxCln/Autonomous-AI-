# Deployment Environment & Secrets

This document lists required environment variables and external dependencies for running the Autonomous AI Agent System in production.

## Required Services
- Database: PostgreSQL (or SQLite for dev)
- Cache/Queue: Redis 7+
- Workers: RQ workers (high/normal/low)
- Monitoring: Prometheus + Grafana
- Tracing: Jaeger (optional)
- Ingress/Proxy: Nginx or K8s Ingress

## Core Environment Variables

### Application
- ENVIRONMENT: production | staging | development
- LOG_LEVEL: INFO | DEBUG | WARNING | ERROR
- MAX_CYCLES: default 100
- USE_REAL_TOOLS: true | false

### Security
- JWT_SECRET_KEY: required in production
- JWT_ALGORITHM: HS256 (default)
- JWT_ACCESS_TOKEN_EXPIRE_MINUTES: default 30
- RATE_LIMIT_REQUESTS: default 100
- RATE_LIMIT_WINDOW: default 60

### Database
- DATABASE_URL: e.g., postgresql://user:pass@db:5432/agent
- DATABASE_URL_US_EAST_1: for multi-region
- DATABASE_URL_US_WEST_2: for multi-region
- DATABASE_URL_EU_WEST_1: for multi-region

### Redis / Queues
- REDIS_URL: redis://redis:6379/0
- RQ_RESULT_TTL: default 3600
- RQ_FAILURE_TTL: default 86400

### Distributed (optional)
- DISTRIBUTED_MESSAGE_NAMESPACE: agent:queues
- DISTRIBUTED_SERVICE_NAMESPACE: agent:services
- DISTRIBUTED_VISIBILITY_TIMEOUT: 30
- DISTRIBUTED_QUEUE_POLL_INTERVAL: 1
- DISTRIBUTED_SERVICE_TTL: 45
- DISTRIBUTED_HEARTBEAT_INTERVAL: 15

### Observability
- ENABLE_METRICS: true
- PROMETHEUS_PORT: 9090
- JAEGER_ENDPOINT: http://jaeger:14268/api/traces

### AI Providers (optional)
- OPENAI_API_KEY
- ANTHROPIC_API_KEY
- SERPAPI_KEY

## Health Verification
Use `scripts/verify_readiness.py` or curl:

```bash
# API
curl -sf $API_BASE/health
curl -sf $API_BASE/api/v1/system/health

# Prometheus
curl -sf http://localhost:9090/-/healthy

# Redis
redis-cli -h $REDIS_HOST -p $REDIS_PORT ping
```

## Kubernetes Secrets (example)
- jwt-secret (JWT_SECRET_KEY)
- db-credentials (DATABASE_URL)
- redis-config (REDIS_URL)
- provider-keys (OPENAI_API_KEY, ANTHROPIC_API_KEY)

## Kubernetes Deployment
- Base manifests + autoscalers live in `k8s/` with a ready-to-apply `kustomization.yaml`
- Replace the placeholders in `k8s/secrets/agent-secrets.yaml` (or wire in your secret manager)
- Deploy with `kubectl apply -k k8s` and monitor rollouts via `kubectl rollout status -n agent-system`
- HPAs (`agent-api-hpa`, `agent-worker-hpa`) keep API/worker replicas between their configured min/max ranges; tune targets per cluster

## Docker Compose Notes
- Ensure `config/docker-compose.yml` mounts `./data` and `./logs`
- Expose ports: API (8000), Redis (6379), Prometheus (9090), Grafana (3000), Jaeger (16686)
