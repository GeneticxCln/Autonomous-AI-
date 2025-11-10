# Production Readiness Checklist

Use this checklist to validate the system before production rollout.

## 1. Build & Tests
- [ ] Dependencies installed (`make install`)
- [ ] Dev tools installed (`make dev`)
- [ ] Lint/typecheck: `ruff check .`, `mypy src.agent_system`
- [ ] Tests passing: `PYTHONPATH=src pytest -q`

## 2. Security
- [ ] `JWT_SECRET_KEY` set in secrets store
- [ ] Admin password rotated (`DEFAULT_ADMIN_PASSWORD` unset)
- [ ] CORS/Rate limiting configured
- [ ] HTTPS/TLS termination enabled at ingress/proxy

## 3. Database
- [ ] `DATABASE_URL` points to managed PostgreSQL
- [ ] Migrations applied (alembic if used)
- [ ] Backups scheduled and tested
- [ ] Connection pooling configured

## 4. Redis & Queues
- [ ] Redis deployed and reachable (`redis-cli ping`)
- [ ] RQ workers running (high/normal/low)
- [ ] Queue metrics exported (rq_* metrics)

## 5. Observability
- [ ] Prometheus reachable (`/-/healthy`)
- [ ] Grafana dashboards imported (overview, workers, throughput)
- [ ] Jaeger UI reachable (optional)
- [ ] Logs shipped to centralized system

## 6. Health Verification
- [ ] `GET /health` returns 200
- [ ] `GET /api/v1/system/health` returns 200
- [ ] `scripts/verify_readiness.py` reports ok=true

## 7. Scaling & HA
- [ ] API replicas >= 2
- [ ] Workers scaled per workload
- [ ] HPA configured for API and workers
- [ ] Readiness/liveness probes configured

## 8. Multi-Region (optional)
- [ ] Region configs set (DATABASE_URL_* per region)
- [ ] Failover strategy documented
- [ ] Data replication validated

## 9. Runbooks
- [ ] On-call runbook created
- [ ] Incident response steps documented
- [ ] Backup/restore procedure documented
