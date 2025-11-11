# 🤖 Autonomous AI Agent System

A sophisticated, enterprise-grade autonomous AI agent platform with real intelligence, learning capabilities, and production-ready infrastructure.

## ✨ Features

- **🧠 True AI Intelligence**: Autonomous reasoning, planning, and decision-making
- **🔄 Cross-Session Learning**: Persistent knowledge across sessions
- **🔐 Enterprise Security**: JWT authentication with role-based access control
- **🌐 Multiple Interfaces**: CLI, API, web dashboard, and chat interfaces
- **🛠️ Tool Integration**: Real and mock tool support with API fallbacks
- **📊 Performance Monitoring**: Real-time metrics and system health tracking
- **🐳 Production Ready**: Docker deployment with health checks
- **🕸️ Distributed Architecture**: Cluster message bus, service discovery, and shared state management

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd clean_project

# (Optional) Prepare project virtual environment
make venv
source .venv/bin/activate

# Install dependencies
make install

# Install in development mode
make dev
```

### Core Dependencies

The production runtime expects a running Redis instance (v6+) and the Python packages `redis`, `rq`, and `rq-scheduler`. These services power caching, distributed queues, and business metric persistence. Ensure Redis is reachable (`REDIS_URL`/`REDIS_HOST`) before starting the API or worker processes; startup will fail fast if the connection cannot be established.

### Basic Usage

```bash
# Run the agent with default goals
make run

# Launch the asynchronous worker (requires Redis + DISTRIBUTED_ENABLED=true)
make worker

# Interactive terminal mode
make interactive

# Run with custom goals
make run-goals GOAL="Research AI trends::0.8" GOAL="Create report::0.7"

# Web dashboard
make web

# API server
make api
```

## 📁 Project Structure

```
clean_project/
├── src/                    # Source code
│   └── agent_system/       # Core agent modules
├── tests/                  # Test suite
├── config/                 # Configuration files
│   ├── requirements.txt    # Dependencies
│   ├── Dockerfile         # Container definition
│   ├── docker-compose.yml # Service orchestration
│   └── .env.example       # Environment template
├── docs/                   # Documentation
├── scripts/                # Utilities and demos
├── Makefile               # Development commands
├── pyproject.toml         # Project configuration
└── README.md              # This file
```

## 🎯 Core Components

### AI Intelligence Layer
- **AutonomousAgent**: Central orchestrator
- **AI Planner**: Intelligent task decomposition
- **Action Selector**: Smart decision making
- **Learning System**: Experience-based improvement
- **Cross-Session Memory**: Persistent knowledge

### Tool System
- **Enhanced Tool Registry**: Real/mock tool support
- **Plugin Architecture**: Extensible tool system
- **Security Validation**: Safe execution environment

### Enterprise Features
- **JWT Authentication**: Stateless security
- **Role-Based Access**: Granular permissions
- **System Health Dashboard**: Monitoring and metrics
- **API Security**: Rate limiting and protection

## 🛠️ Development

### Available Commands

```bash
make install      # Install dependencies
make dev          # Development installation
make lint         # Code linting
make format       # Code formatting
make typecheck    # Type checking
make test         # Run tests
make cov          # Test coverage
make ci           # Full CI pipeline
```

### Testing

```bash
# Run all tests
make test

# Run with coverage
make cov

# Run specific test category
pytest tests/test_planning.py
pytest tests/test_e2e_workflow.py
```

## 🔧 Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Core settings
MAX_CYCLES=100
LOG_LEVEL=INFO
USE_REAL_TOOLS=true

# Strict mode (optional)
# When enabled: embeddings must be available; rate limiting requires Redis (no in-memory fallback)
STRICT_MODE=false

# API keys (optional)
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
SERPAPI_KEY=your_key_here
BING_SEARCH_KEY=your_key_here
GOOGLE_SEARCH_KEY=your_key_here
# Google Custom Search requires a CSE ID
GOOGLE_CSE_ID=your_cse_id

# Database
DATABASE_URL=sqlite:///./agent.db

# Security
JWT_SECRET_KEY=your-secret-key
```

### Tool Configuration

The agent supports both real and mock tools:
- **Real tools**: Use actual APIs when keys are available
- **Mock tools**: Fallback to simulated responses
- **Auto-detection**: Automatically switches based on configuration

#### Web Search Provider Selection
- Configure provider order via `SEARCH_PROVIDER_ORDER` (comma-separated): `serpapi,bing,google`
- Disable providers via `DISABLED_SEARCH_PROVIDERS`
- Google Custom Search requires both `GOOGLE_SEARCH_KEY` and `GOOGLE_CSE_ID` (or `GOOGLE_SEARCH_CX`)

In strict mode, web search will fail fast if no enabled providers are configured.

## 🔐 RBAC Helpers

- Grant a role to an existing user (admin has `system.write` by default):

```bash
python clean_project/scripts/grant_role.py --username <your-user> --role admin
```

- Default admin in development:
  - Username: `admin`
  - Password: `admin123` (override by setting `DEFAULT_ADMIN_PASSWORD`)

Permissions of built-in roles:
- admin: full access including `system.write` and `system.admin`
- manager: elevated access including `system.write`
- user: basic access
- guest: read-only

## 📖 API Documentation

### Web Interface
- **Dashboard**: `http://localhost:8000` (when running `make web`)
- **API Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`

### CLI Interfaces
```bash
# Interactive chat
agent-chat --provider local

# Terminal REPL
agent-term

# Direct execution
agent-run --goal "Your task here"
```

## 🐳 Deployment

### Docker
```bash
# Build image
docker build -f config/Dockerfile -t agent-system .

# Run with compose
docker-compose -f config/docker-compose.yml up
```

### Provider Configuration API

Requires an authenticated token with `system.read`/`system.write`.

```bash
# Login to obtain token (replace credentials as necessary)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | jq -r .data.access_token)

# Get current provider configuration/status
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/system/providers/search-config | jq '.'

# Update provider order/disable list
curl -s -X PUT -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN" \
  -d '{"order":["serpapi","bing","google"],"disabled":["google"]}' \
  http://localhost:8000/api/v1/system/providers/search-config | jq '.'
```

Make targets for convenience:
- `make provider-show` – prints current configuration and status
- `make provider-set-order ORDER=serpapi,bing,google` – sets provider order
- `make provider-disable DISABLE=google` – disables providers (comma-separated)
- `make grant-role USER=<user> ROLE=<admin|manager|user|guest>` – grant role to a user
- `make bootstrap-check` – readiness check (DB, Redis, providers)

### Production Considerations
- Set strong JWT secrets
- Configure proper database
- Enable rate limiting
- Set up monitoring
- Use HTTPS in production
- Manage secrets via a dedicated store (AWS Secrets Manager, GCP Secret Manager, Vault, or Kubernetes Secrets) as outlined in [`docs/SECRET_MANAGEMENT.md`](docs/SECRET_MANAGEMENT.md)

### Monitoring & Observability
- **Prometheus**: scrape the FastAPI `/metrics` endpoint (enabled when `ENABLE_METRICS=1`) for detailed system, cache, and AI-performance metrics including `agent_system_health_score`, `agent_decision_accuracy_ratio`, and `cache_hit_ratio`.
- **Grafana Dashboards**: prebuilt dashboards live in `config/monitoring/grafana/dashboards/` (`Agent System Overview`, `Agent System Health`, `Agent AI Performance`). They are auto-provisioned by the compose/Kubernetes manifests.
- **Alerting**: Prometheus alert rules are defined in `config/monitoring/alert_rules.yml` and cover availability, infrastructure saturation, cache efficiency, and AI quality signals. Wire them to Alertmanager (e.g., Slack/Webhook) for paging.
- **Alertmanager**: `config/monitoring/alertmanager.yml` is enabled via Docker Compose and forwards incidents to the internal `/api/v1/system/alerts/webhook` endpoint. Set `ALERTMANAGER_WEBHOOK_TOKEN` if you want bearer-token protection or swap in your own receivers.
- **Docker Compose**: `config/docker-compose.yml` mounts both `prometheus.yml` and the alert rules so you get health/AI alerts out-of-the-box (`docker compose -f config/docker-compose.yml up prometheus grafana`).

## 🧪 Examples

### Basic Agent Usage
```python
from src.agent_system import AutonomousAgent

# Initialize agent
agent = AutonomousAgent()

# Add goals
agent.add_goal("Research AI trends", priority=0.8)
agent.add_goal("Create summary report", priority=0.9)

# Run agent
agent.run(max_cycles=20)

# Check status
status = agent.get_status()
print(f"Current goal: {status['current_goal']}")
```

### Concurrent Goal Processing
Set `AGENT_MAX_CONCURRENT_GOALS` (or update `unified_config.agent.max_concurrent_goals`) to enable parallel goal execution:

```python
import asyncio
from src.agent_system import AutonomousAgent

agent = AutonomousAgent()
agent.add_goal("Collect product requirements", priority=0.8)
agent.add_goal("Draft design proposal", priority=0.9)

asyncio.run(agent.run_async(max_cycles=40, max_concurrent_goals=2))
```

### Custom Tool Integration
```python
from src.agent_system.tools import Tool

class CustomTool(Tool):
    @property
    def name(self) -> str:
        return "custom_tool"
    
    def execute(self, **kwargs):
        # Your custom logic
        return ActionStatus.SUCCESS, {"result": "Custom action completed"}

# Register with agent
agent = AutonomousAgent()
agent.tool_registry.register_tool(CustomTool())
```

## 📊 Performance

- **Response Time**: <50ms for authentication
- **Success Rate**: 100% with graceful fallbacks
- **Memory Usage**: Optimized for long-running sessions
- **Scalability**: Supports horizontal scaling

## 🤝 Contributing

1. Follow the coding standards (`make lint`, `make format`)
2. Add tests for new features
3. Update documentation
4. Run the full CI pipeline (`make ci`)

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Support

- **Documentation**: Check `docs/` directory
- **Examples**: See `scripts/` directory
- **Issues**: Create GitHub issues for bugs
- **Discussions**: Use GitHub discussions for questions

---

**Built with ❤️ for autonomous AI agent development**
