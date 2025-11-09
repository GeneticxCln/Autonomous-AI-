# ADR-001: Stateless API Tier and Dedicated Worker Entrypoint

## Status
- **Proposed:** 2025-01-27
- **Decision Makers:** Platform & AI Systems leads
- **Related Roadmap Item:** `ENTERPRISE_SCALING_ROADMAP.md` Track A1 / Track C1

## Context
- `src/agent_system/fastapi_app.py` currently embeds planner/executor logic, meaning each API replica runs long-lived agent loops.
- Background execution primitives exist (`task_queue.py`, `distributed_message_queue.py`, `service_registry.py`) but are tightly coupled to the monolithic process.
- Horizontal scaling requires the HTTP tier to remain stateless so Kubernetes/Docker replicas can scale independently and rely on shared queues/state.
- Workers must expose health endpoints and structured logging so load balancers can drain pods without corrupting in-flight jobs.

## Decision
1. **Split Roles:** FastAPI service handles request validation, enqueues jobs via `DistributedMessageQueue`/RQ, and streams back job status only. Planner/executor/learning loops run in isolated worker processes.
2. **New Worker Entrypoint:** Add `python -m agent_system.worker` (and `scripts/run_worker.py`) that bootstraps logging, loads `agent.AgentConfig`, registers with `service_registry`, then listens on high/normal/low queues.
3. **Shared Job Contract:** Define Pydantic payloads in `agent_system/job_definitions.py` for planner/execution/error-reporting so API and worker stay versioned together. Contracts include tenant, auth context, tool scopes, and callback URL/topic.
4. **State Externalization:** Agent, goal, and observation state persist via `enterprise_persistence.py` (PostgreSQL + Redis cache). Workers never rely on in-process memory for durable data.
5. **Observability Hooks:** API and workers emit Prometheus metrics (`queue_depth`, `job_latency`, `worker_heartbeat`) and expose `/health` + `/ready` endpoints. These metrics will drive HPAs.

## Consequences
- **Positive:** Enables independent scaling of API vs worker pools, simplifies rolling updates, and prepares for autoscaling based on queue depth.
- **Trade-offs:** Adds network hops and requires reliable Redis/RQ. Local dev stack needs Docker Compose profiles for api/worker parity.
- **Risks:** Misaligned job versions could break workflows. Mitigation: shared package + contract tests (`tests/test_distributed_architecture.py`).

## Implementation Plan
1. **Module Work**
   - Move long-running planner/executor loops from `fastapi_app.py` into new `worker.py`.
   - Add job schema module + serialization helpers.
   - Ensure `task_queue.TaskQueueManager` exposes CLI-friendly worker bootstrapping.
2. **Process Management**
   - Extend `Makefile`/`docker-compose.yml` with `api` and `worker` services.
   - Add Kubernetes Deployments (`k8s/deployments/api.yaml`, `k8s/deployments/worker.yaml`) with independent HPAs.
3. **API Adjustments**
   - Request handlers persist job metadata to DB, enqueue RQ jobs, immediately return `202 Accepted` with job id.
   - Add polling/SSE endpoints so clients can fetch results without sticky sessions.
4. **Observability**
   - Instrument queue metrics + worker heartbeat using `ai_performance_monitor.py` and export via `/metrics`.
5. **Testing & Rollout**
   - Update `tests/test_distributed_architecture.py` to cover job enqueue/consume path.
   - Provide migration guide in `docs/PRODUCTION_DEPLOYMENT_GUIDE.md`.

## Open Questions
1. Should we adopt Celery (AMQP) vs. stay on Redis/RQ? Initial decision is RQ for lower lift; revisit after load tests.
2. Do we need strong ordering guarantees per tenant? If yes, implement keyed queues or sharding strategy.
3. How should job cancellation be propagated? Requires control channel between API and workers.
