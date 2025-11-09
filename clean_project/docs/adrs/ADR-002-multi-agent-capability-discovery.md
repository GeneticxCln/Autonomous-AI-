# ADR-002: Multi-Agent Capability Discovery Service

## Status
- **Proposed:** 2025-01-27
- **Decision Makers:** AI Systems lead, Enterprise Readiness lead
- **Related Roadmap Item:** `ENTERPRISE_SCALING_ROADMAP.md` Pillar 2, MA1

## Context
- `multi_agent_system.AgentRegistry` currently seeds static agents at process start; no cluster-wide view exists.
- Planned multi-agent collaboration requires workers to advertise roles/capabilities so planners can dynamically allocate tasks.
- `service_registry.py` already maintains liveness info in Redis; `distributed_message_queue.py` provides messaging.
- Enterprises will run heterogeneous agent workers (knowledge-focused vs action-focused) and need auditable capability metadata.

## Decision
1. **Capability Registry:** Persist agent identities, roles, expertise domains, capacity, and supported tool scopes in PostgreSQL (new `agent_capabilities` table) with Redis cache for fast lookup.
2. **Discovery API:** Expose REST endpoints (`/api/v1/agents/capabilities`) plus internal gRPC/Redis pub-sub channel so workers can register/unregister at runtime. Workers submit signed capability manifests during startup.
3. **Planner Integration:** `ai_planner.py` queries the capability registry when decomposing goals; selection logic prefers agents whose declared capacity > active tasks and whose domains match the goal taxonomy.
4. **Security & Audit:** All capability registration calls require service-to-service auth (JWT with `agent.register` scope). Changes are logged via `advanced_security.SecurityEvent`.
5. **Schema Standardization:** Define `AgentCapabilityDescriptor` (Pydantic) reused by API responses, worker manifests, and `multi_agent_system.py`.

## Consequences
- **Positive:** Enables dynamic collaboration, better utilization, and future marketplace integrations.
- **Trade-offs:** Requires additional persistence + auth flows and increases worker startup complexity.
- **Risks:** Stale capability data could misroute tasks; mitigate via TTL heartbeats synced with `service_registry`.

## Implementation Plan
1. **Data Layer**
   - Add migrations for `agent_capabilities`, `agent_capability_history`, and `agent_workload` tables.
   - Extend `enterprise_persistence.py` with CRUD methods and caching helpers.
2. **Worker Manifest**
   - Create `agent_system/agent_manifest.py` to load capabilities from config/env; publish on startup and refresh periodically.
   - Hook into worker shutdown to deregister capabilities.
3. **API & Planner**
   - Build FastAPI routes for capability CRUD + search filters (role, expertise, location, tenant).
   - Update `ai_planner.py` and `multi_agent_system.py` to fetch from capability registry instead of static defaults.
4. **Messaging**
   - Broadcast capability changes over `distributed_message_queue` topics so planners refresh caches without polling.
5. **Tests & Docs**
   - Add unit tests in `tests/test_multi_agent_capabilities.py`.
   - Document the manifest format + registration flow in `docs/ENTERPRISE_SCALING_ROADMAP.md` (MA1) and new developer guide.

## Open Questions
1. Do we need approval workflows before new capabilities go live (e.g., security review)?
2. Should capacity be weighted by performance metrics (success rate, latency) for smarter routing?
3. How do we handle tenants that restrict which agents can process their data (data residency / confidentiality constraints)?
