# Autonomous Agent System

An experimental, self-contained Python agent that demonstrates a full autonomy loop: hierarchical planning, goal management, action selection, tool execution, memory, observation analysis, and learning.

## Quick Start
- Ensure Python 3.9+ is available.
- Execute the demo run: `python3 -m agent_system`
- Inspect the structured status report printed at the end for memory, tool, and learning statistics.

### CLI Options
- `--max-cycles N` — cap the loop to N iterations (default `20`).
- `--goal "Description::priority"` — seed a goal; repeat to add more (priority clamped to `0.0–1.0`, default `0.5` if omitted).
- `--log-level LEVEL` — set logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
- Example:  
  `python3 -m agent_system --max-cycles 10 --goal "Draft blog post::0.7" --goal "Review references::0.4" --log-level DEBUG`

## Architecture
- **`agent_system.models`**: Dataclasses for goals, plans, actions, observations, and memories plus status enums.
- **`agent_system.planning`**: `HierarchicalPlanner` HTN decomposition and action parameter assembly.
- **`agent_system.goal_manager`**: Priority-queue goal tracker with dependency handling and hierarchy export.
- **`agent_system.action_selector`**: Scoring-based selector with lightweight reinforcement learning updates.
- **`agent_system.tools`**: Abstract tool API, mock tool implementations, and the retry-aware `ToolRegistry`.
- **`agent_system.memory`**: Working/episodic memory manager and context summariser.
- **`agent_system.observation`**: Observation analyzer with anomaly detection hooks.
- **`agent_system.learning`**: Episode-level strategy tracking and improvement suggestions.
- **`agent_system.agent`**: `AutonomousAgent` orchestrator that binds every subsystem together.

## Customising Goals & Actions
- Pass `constraints` when adding goals to steer tool parameters (e.g., `filepath`, `query`, `code`).
- Extend `HierarchicalPlanner._init_action_templates` or add new decomposition rules to introduce domain-specific behaviour.
- Register real tools by subclassing `Tool` and hooking them into `_register_default_tools`.

## Next Steps
- API & docs: add OpenAPI examples and error schemas, surface the typed envelope in docs, and flesh out usage guides.
- Migrations & DB: document Alembic workflow; provide Postgres deployment config and a migration runbook; ensure migrate step in CI/CD.
- Performance & observability: create load tests and baselines; ship Prometheus dashboards and add tracing for tool/DB calls.
- Security & secrets: use env/secret manager for JWT/DB, rotate keys, expand CI scans (SAST/DAST) alongside Trivy.
- Plugin ecosystem: document plugin YAML/JSON and optional entry-point discovery; publish example plugins and templates.

## Recently Completed
- Replace mock tools with real integrations and add richer observation metrics (latency, payload/result sizes, attempts).
- Add configuration files and plugin discovery (YAML/JSON) for registering custom tools/goals, auto-loaded from `.agent_plugins.yaml`.
- Wire in linting/formatting (ruff, black, mypy) and CI to enforce tests automatically (plus container scan).

## Testing
- Run the suite with `python3 -m unittest discover`.

## Terminal Chat Agent
- Start: `agent-chat --provider local`
- Help: inside chat, run `/help`
- Examples:
  - `/ls`, `/pwd`, `/cat README.md`
  - `/format .`, `/lint .`, `/tests`
  - `/plan "Refactor tools and run tests"` then `/runplan`
